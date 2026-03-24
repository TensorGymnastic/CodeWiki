"""
CLI adapter for documentation generator backend.

This adapter wraps the existing backend documentation_generator.py
and provides CLI-specific functionality like progress reporting.

Supports iterative documentation generation when existing documentation
is detected (metadata.json with commit_id exists).
"""

from pathlib import Path
from typing import Dict, Any, Optional
import time
import asyncio
import os
import logging
import sys


from codewiki.cli.utils.progress import ProgressTracker
from codewiki.cli.models.job import DocumentationJob, LLMConfig
from codewiki.cli.utils.errors import APIError

# Import backend modules
from codewiki.src.be.documentation_generator import DocumentationGenerator
from codewiki.src.be.iterative import IterativeDocumentationGenerator
from codewiki.src.config import Config as BackendConfig, set_cli_context


class CLIDocumentationGenerator:
    """
    CLI adapter for documentation generation with progress reporting.
    
    This class wraps the backend documentation generator and adds
    CLI-specific features like progress tracking and error handling.
    
    Supports iterative generation when existing documentation is detected.
    """
    
    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        config: Dict[str, Any],
        verbose: bool = False,
        generate_html: bool = False,
        force_full: bool = False,
        from_commit: Optional[str] = None
    ):
        """
        Initialize the CLI documentation generator.
        
        Args:
            repo_path: Repository path
            output_dir: Output directory
            config: LLM configuration
            verbose: Enable verbose output
            generate_html: Whether to generate HTML viewer
            force_full: Force full regeneration (ignore existing docs)
            from_commit: Override stored commit for iterative generation
        """
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.config = config
        self.verbose = verbose
        self.generate_html = generate_html
        self.force_full = force_full
        self.from_commit = from_commit
        self.progress_tracker = ProgressTracker(total_stages=5, verbose=verbose)
        self.job = DocumentationJob()
        self._is_iterative = False  # Will be set during generation
        
        # Setup job metadata
        self.job.repository_path = str(repo_path)
        self.job.repository_name = repo_path.name
        self.job.output_directory = str(output_dir)
        self.job.llm_config = LLMConfig(
            main_model=config.get('main_model', ''),
            cluster_model=config.get('cluster_model', ''),
            base_url=config.get('base_url', '')
        )
        
        # Configure backend logging
        self._configure_backend_logging()
    
    def _configure_backend_logging(self):
        """Configure backend logger for CLI use with colored output."""
        from codewiki.src.be.dependency_analyzer.utils.logging_config import ColoredFormatter
        
        # Get backend logger (parent of all backend modules)
        backend_logger = logging.getLogger('codewiki.src.be')
        
        # Remove existing handlers to avoid duplicates
        backend_logger.handlers.clear()
        
        if self.verbose:
            # In verbose mode, show INFO and above
            backend_logger.setLevel(logging.INFO)
            
            # Create console handler with formatting
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # Use colored formatter for better readability
            colored_formatter = ColoredFormatter()
            console_handler.setFormatter(colored_formatter)
            
            # Add handler to logger
            backend_logger.addHandler(console_handler)
        else:
            # In non-verbose mode, suppress backend logs (use WARNING level to hide INFO/DEBUG)
            backend_logger.setLevel(logging.WARNING)
            
            # Create console handler for warnings and errors only
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            
            # Use colored formatter even for warnings/errors
            colored_formatter = ColoredFormatter()
            console_handler.setFormatter(colored_formatter)
            
            backend_logger.addHandler(console_handler)
        
        # Prevent propagation to root logger to avoid duplicate messages
        backend_logger.propagate = False
    
    def _should_use_iterative(self) -> bool:
        """
        Determine if iterative generation should be used.
        
        Returns:
            True if conditions for iterative generation are met
        """
        if self.force_full:
            return False
        
        # Check if metadata exists with commit_id
        metadata_path = self.output_dir / "metadata.json"
        if not metadata_path.exists():
            return False
        
        try:
            from codewiki.src.utils import file_manager
            metadata = file_manager.load_json(str(metadata_path))
            commit_id = metadata.get("generation_info", {}).get("commit_id")
            if not commit_id:
                return False
            
            # Check if module_tree exists
            module_tree_path = self.output_dir / "module_tree.json"
            if not module_tree_path.exists():
                return False
            
            return True
        except Exception:
            return False
    
    def generate(self) -> DocumentationJob:
        """
        Generate documentation with progress tracking.
        
        Automatically detects if iterative generation should be used
        based on existing metadata.json and module_tree.json.
        
        Returns:
            Completed DocumentationJob
            
        Raises:
            APIError: If LLM API call fails
        """
        self.job.start()
        start_time = time.time()
        
        try:
            # Set CLI context for backend
            set_cli_context(True)
            
            # Determine generation mode
            self._is_iterative = self._should_use_iterative()
            
            # Create backend config with CLI settings
            backend_config = BackendConfig.from_cli(
                repo_path=str(self.repo_path),
                output_dir=str(self.output_dir),
                llm_base_url=self.config.get('base_url'),
                llm_api_key=self.config.get('api_key'),
                main_model=self.config.get('main_model'),
                cluster_model=self.config.get('cluster_model'),
                fallback_model=self.config.get('fallback_model'),
                max_tokens=self.config.get('max_tokens', 32768),
                max_token_per_module=self.config.get('max_token_per_module', 36369),
                max_token_per_leaf_module=self.config.get('max_token_per_leaf_module', 16000),
                max_depth=self.config.get('max_depth', 2),
                agent_instructions=self.config.get('agent_instructions')
            )
            
            # Run backend documentation generation
            if self._is_iterative:
                asyncio.run(self._run_iterative_generation(backend_config))
            else:
                asyncio.run(self._run_backend_generation(backend_config))
            
            # Stage 4: HTML Generation (optional)
            if self.generate_html:
                self._run_html_generation()
            
            # Stage 5: Finalization (metadata already created by backend)
            self._finalize_job()
            
            # Complete job
            generation_time = time.time() - start_time
            self.job.complete()
            
            return self.job
            
        except APIError as e:
            self.job.fail(str(e))
            raise
        except Exception as e:
            self.job.fail(str(e))
            raise
    
    async def _run_backend_generation(self, backend_config: BackendConfig):
        """Run the backend documentation generation with progress tracking."""
        
        # Stage 1: Dependency Analysis
        self.progress_tracker.start_stage(1, "Dependency Analysis")
        if self.verbose:
            self.progress_tracker.update_stage(0.2, "Initializing dependency analyzer...")
        
        # Create documentation generator
        doc_generator = DocumentationGenerator(backend_config)
        
        if self.verbose:
            self.progress_tracker.update_stage(0.5, "Parsing source files...")
        
        # Build dependency graph
        try:
            components, leaf_nodes = doc_generator.graph_builder.build_dependency_graph()
            self.job.statistics.total_files_analyzed = len(components)
            self.job.statistics.leaf_nodes = len(leaf_nodes)
            
            if self.verbose:
                self.progress_tracker.update_stage(1.0, f"Found {len(leaf_nodes)} leaf nodes")
        except Exception as e:
            raise APIError(f"Dependency analysis failed: {e}")
        
        self.progress_tracker.complete_stage()
        
        # Stage 2: Module Clustering
        self.progress_tracker.start_stage(2, "Module Clustering")
        if self.verbose:
            self.progress_tracker.update_stage(0.5, "Clustering modules with LLM...")
        
        # Import clustering function
        from codewiki.src.be.cluster_modules import cluster_modules
        from codewiki.src.utils import file_manager
        from codewiki.src.config import FIRST_MODULE_TREE_FILENAME, MODULE_TREE_FILENAME
        
        working_dir = str(self.output_dir.absolute())
        file_manager.ensure_directory(working_dir)
        first_module_tree_path = os.path.join(working_dir, FIRST_MODULE_TREE_FILENAME)
        module_tree_path = os.path.join(working_dir, MODULE_TREE_FILENAME)
        
        try:
            if os.path.exists(first_module_tree_path):
                module_tree = file_manager.load_json(first_module_tree_path)
            else:
                module_tree = cluster_modules(leaf_nodes, components, backend_config)
                file_manager.save_json(module_tree, first_module_tree_path)
            
            file_manager.save_json(module_tree, module_tree_path)
            self.job.module_count = len(module_tree)
            
            if self.verbose:
                self.progress_tracker.update_stage(1.0, f"Created {len(module_tree)} modules")
        except Exception as e:
            raise APIError(f"Module clustering failed: {e}")
        
        self.progress_tracker.complete_stage()
        
        # Stage 3: Documentation Generation
        self.progress_tracker.start_stage(3, "Documentation Generation")
        if self.verbose:
            self.progress_tracker.update_stage(0.1, "Generating module documentation...")
        
        try:
            # Run the actual documentation generation
            await doc_generator.generate_module_documentation(components, leaf_nodes)
            
            if self.verbose:
                self.progress_tracker.update_stage(0.9, "Creating repository overview...")
            
            # Create metadata
            doc_generator.create_documentation_metadata(working_dir, components, len(leaf_nodes))
            
            # Collect generated files
            for file_path in os.listdir(working_dir):
                if file_path.endswith('.md') or file_path.endswith('.json'):
                    self.job.files_generated.append(file_path)
            
        except Exception as e:
            raise APIError(f"Documentation generation failed: {e}")
        
        self.progress_tracker.complete_stage()
    
    async def _run_iterative_generation(self, backend_config: BackendConfig):
        """Run iterative documentation generation with progress tracking."""
        
        # Stage 1: Change Detection
        self.progress_tracker.start_stage(1, "Change Detection")
        if self.verbose:
            self.progress_tracker.update_stage(0.2, "Detecting changes since last generation...")
        
        # Create iterative generator
        iterative_generator = IterativeDocumentationGenerator(backend_config)
        
        if self.verbose:
            self.progress_tracker.update_stage(0.5, "Analyzing git history...")
        
        # Check if iterative is actually possible
        if not iterative_generator.should_use_iterative():
            if self.verbose:
                self.progress_tracker.update_stage(1.0, "Falling back to full generation")
            self.progress_tracker.complete_stage()
            # Fall back to full generation
            await self._run_backend_generation(backend_config)
            return
        
        if self.verbose:
            self.progress_tracker.update_stage(1.0, "Changes detected, using iterative mode")
        
        self.progress_tracker.complete_stage()
        
        # Stage 2: Dependency Analysis (for new/modified files)
        self.progress_tracker.start_stage(2, "Dependency Analysis")
        if self.verbose:
            self.progress_tracker.update_stage(0.5, "Parsing affected source files...")
        
        try:
            # Build dependency graph for current state
            components, leaf_nodes = iterative_generator.graph_builder.build_dependency_graph()
            self.job.statistics.total_files_analyzed = len(components)
            self.job.statistics.leaf_nodes = len(leaf_nodes)
            
            if self.verbose:
                self.progress_tracker.update_stage(1.0, f"Found {len(leaf_nodes)} leaf nodes")
        except Exception as e:
            raise APIError(f"Dependency analysis failed: {e}")
        
        self.progress_tracker.complete_stage()
        
        # Stage 3: Iterative Documentation Update
        self.progress_tracker.start_stage(3, "Documentation Update")
        if self.verbose:
            self.progress_tracker.update_stage(0.1, "Updating affected module documentation...")
        
        working_dir = str(self.output_dir.absolute())
        
        try:
            # Run iterative generation
            await iterative_generator.run(
                force_full=self.force_full,
                from_commit=self.from_commit
            )
            
            if self.verbose:
                self.progress_tracker.update_stage(0.9, "Finalizing documentation updates...")
            
            # Collect generated/updated files
            for file_path in os.listdir(working_dir):
                if file_path.endswith('.md') or file_path.endswith('.json'):
                    if file_path not in self.job.files_generated:
                        self.job.files_generated.append(file_path)
            
        except Exception as e:
            raise APIError(f"Iterative documentation generation failed: {e}")
        
        self.progress_tracker.complete_stage()
    
    def _run_html_generation(self):
        """Run HTML generation stage."""
        self.progress_tracker.start_stage(4, "HTML Generation")
        
        from codewiki.cli.html_generator import HTMLGenerator
        
        # Generate HTML
        html_generator = HTMLGenerator()
        
        if self.verbose:
            self.progress_tracker.update_stage(0.3, "Loading module tree and metadata...")
        
        repo_info = html_generator.detect_repository_info(self.repo_path)
        
        # Generate HTML with auto-loading of module_tree and metadata from docs_dir
        output_path = self.output_dir / "index.html"
        html_generator.generate(
            output_path=output_path,
            title=repo_info['name'],
            repository_url=repo_info['url'],
            github_pages_url=repo_info['github_pages_url'],
            docs_dir=self.output_dir  # Auto-load module_tree and metadata from here
        )
        
        self.job.files_generated.append("index.html")
        
        if self.verbose:
            self.progress_tracker.update_stage(1.0, "Generated index.html")
        
        self.progress_tracker.complete_stage()
    
    def _finalize_job(self):
        """Finalize the job (metadata already created by backend)."""
        # Just verify metadata exists
        metadata_path = self.output_dir / "metadata.json"
        if not metadata_path.exists():
            # Create our own if backend didn't
            with open(metadata_path, 'w') as f:
                f.write(self.job.to_json())

