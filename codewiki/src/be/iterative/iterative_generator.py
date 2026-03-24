"""
Iterative documentation generator orchestrator.

This module coordinates the iterative documentation generation process,
handling change detection, module tree updates, and documentation propagation.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from codewiki.src.config import Config, MODULE_TREE_FILENAME, FIRST_MODULE_TREE_FILENAME
from codewiki.src.be.dependency_analyzer import DependencyGraphBuilder
from codewiki.src.be.dependency_analyzer.models.core import Node
from codewiki.src.be.agent_orchestrator import AgentOrchestrator
from codewiki.src.be.iterative.change_detector import (
    ChangeDetector, 
    ChangeClassification, 
    ChangeType,
    AffectedComponents
)
from codewiki.src.be.iterative.module_tree_updater import ModuleTreeUpdater
from codewiki.src.be.iterative.doc_propagator import DocPropagator, UpdateResult
from codewiki.src.utils import file_manager

logger = logging.getLogger(__name__)


class IterativeDocumentationGenerator:
    """Orchestrates iterative documentation generation."""
    
    def __init__(self, config: Config, commit_id: Optional[str] = None):
        """
        Initialize the iterative documentation generator.
        
        Args:
            config: Configuration object
            commit_id: Target commit ID (default: HEAD)
        """
        self.config = config
        self.target_commit = commit_id
        self.working_dir = os.path.abspath(config.docs_dir)
        
        # Initialize sub-components
        self.graph_builder = DependencyGraphBuilder(config)
        self.change_detector = ChangeDetector(config.repo_path, config)
        self.tree_updater = ModuleTreeUpdater(config)
        self.agent_orchestrator = AgentOrchestrator(config)
    
    def load_metadata(self) -> Optional[Dict[str, Any]]:
        """Load existing metadata from the docs directory."""
        metadata_path = os.path.join(self.working_dir, "metadata.json")
        if os.path.exists(metadata_path):
            return file_manager.load_json(metadata_path)
        return None
    
    def load_module_tree(self) -> Optional[Dict[str, Any]]:
        """Load existing module tree from the docs directory."""
        module_tree_path = os.path.join(self.working_dir, MODULE_TREE_FILENAME)
        if os.path.exists(module_tree_path):
            return file_manager.load_json(module_tree_path)
        return None
    
    def save_module_tree(self, module_tree: Dict[str, Any]) -> None:
        """Save module tree to the docs directory."""
        module_tree_path = os.path.join(self.working_dir, MODULE_TREE_FILENAME)
        file_manager.save_json(module_tree, module_tree_path)
    
    def get_stored_commit(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract the stored commit ID from metadata."""
        return metadata.get("generation_info", {}).get("commit_id")
    
    def update_metadata(
        self,
        metadata: Dict[str, Any],
        from_commit: str,
        to_commit: str,
        change_type: ChangeType,
        affected_modules: List[List[str]],
        summary: str
    ) -> Dict[str, Any]:
        """
        Update metadata with iterative generation info.
        
        Args:
            metadata: Existing metadata
            from_commit: Starting commit
            to_commit: Ending commit
            change_type: Type of change processed
            affected_modules: List of affected module paths
            summary: Summary of changes made
            
        Returns:
            Updated metadata
        """
        # Update generation info
        metadata["generation_info"]["commit_id"] = to_commit
        metadata["generation_info"]["timestamp"] = datetime.now().isoformat()
        metadata["generation_info"]["generation_type"] = "iterative"
        
        # Add to iterative history
        if "iterative_history" not in metadata:
            metadata["iterative_history"] = []
        
        metadata["iterative_history"].append({
            "timestamp": datetime.now().isoformat(),
            "from_commit": from_commit,
            "to_commit": to_commit,
            "change_type": change_type.value,
            "affected_modules": ["/".join(path) for path in affected_modules],
            "summary": summary
        })
        
        # Keep only last 50 entries
        if len(metadata["iterative_history"]) > 50:
            metadata["iterative_history"] = metadata["iterative_history"][-50:]
        
        return metadata
    
    def save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save metadata to the docs directory."""
        metadata_path = os.path.join(self.working_dir, "metadata.json")
        file_manager.save_json(metadata, metadata_path)
    
    def should_use_iterative(self) -> bool:
        """
        Determine if iterative generation should be used.
        
        Returns:
            True if conditions for iterative generation are met
        """
        # Check if metadata exists
        metadata = self.load_metadata()
        if not metadata:
            logger.info("No existing metadata found - will use full generation")
            return False
        
        # Check if commit ID is stored
        stored_commit = self.get_stored_commit(metadata)
        if not stored_commit:
            logger.info("No stored commit ID in metadata - will use full generation")
            return False
        
        # Check if commit is valid
        if not self.change_detector.is_commit_valid(stored_commit):
            logger.warning(f"Stored commit {stored_commit} not found in git history - will use full generation")
            return False
        
        # Check if module tree exists
        module_tree = self.load_module_tree()
        if not module_tree:
            logger.info("No existing module tree found - will use full generation")
            return False
        
        return True
    
    async def run(self, force_full: bool = False, from_commit: Optional[str] = None) -> str:
        """
        Run documentation generation (iterative if possible).
        
        Args:
            force_full: If True, force full regeneration
            from_commit: Override stored commit (for iterative only)
            
        Returns:
            Path to the output directory
        """
        file_manager.ensure_directory(self.working_dir)
        
        # Determine if we should use iterative generation
        if force_full or not self.should_use_iterative():
            logger.info("Using full documentation generation")
            return await self._run_full_generation()
        
        logger.info("Using iterative documentation generation")
        return await self._run_iterative_generation(from_commit)
    
    async def _run_full_generation(self) -> str:
        """Run full documentation generation (delegates to existing generator)."""
        from codewiki.src.be.documentation_generator import DocumentationGenerator
        
        current_commit = self.change_detector.get_current_commit()
        generator = DocumentationGenerator(self.config, commit_id=current_commit)
        await generator.run()
        
        return self.working_dir
    
    async def _run_iterative_generation(self, from_commit: Optional[str] = None) -> str:
        """
        Run iterative documentation generation.
        
        Args:
            from_commit: Override stored commit
            
        Returns:
            Path to the output directory
        """
        # Load existing data
        metadata = self.load_metadata()
        module_tree = self.load_module_tree()
        
        # Determine commits
        stored_commit = from_commit or self.get_stored_commit(metadata)
        current_commit = self.target_commit or self.change_detector.get_current_commit()
        
        if not stored_commit or not current_commit:
            logger.error("Could not determine commit range")
            return await self._run_full_generation()
        
        if stored_commit == current_commit:
            logger.info("No new commits since last generation")
            return self.working_dir
        
        logger.info(f"Processing changes from {stored_commit[:8]} to {current_commit[:8]}")
        
        # Build new dependency graph to get current components
        components, leaf_nodes = self.graph_builder.build_dependency_graph()
        
        # Build existing components map from module tree
        existing_components = self._extract_components_from_tree(module_tree, components)
        
        # Detect and classify changes
        classification = self.change_detector.detect_changes(
            from_commit=stored_commit,
            existing_components=existing_components,
            new_components=components,
            module_tree=module_tree,
            to_commit=current_commit
        )
        
        if not classification:
            logger.info("No relevant changes detected")
            # Still update commit ID
            metadata = self.update_metadata(
                metadata, stored_commit, current_commit,
                ChangeType.COMPONENT_CHANGE, [], "No relevant changes"
            )
            self.save_metadata(metadata)
            return self.working_dir
        
        # Process based on change type
        if classification.is_component_change:
            results = await self._handle_component_change(
                classification, module_tree, components, stored_commit
            )
        elif classification.is_minor_revision:
            results, module_tree = await self._handle_minor_revision(
                classification, module_tree, components, leaf_nodes, stored_commit
            )
        else:  # major_revision
            results, module_tree = await self._handle_major_revision(
                classification, module_tree, components, leaf_nodes, stored_commit
            )
        
        # Save updated module tree
        self.save_module_tree(module_tree)
        
        # Update and save metadata
        summary = self._create_update_summary(results)
        metadata = self.update_metadata(
            metadata, stored_commit, current_commit,
            classification.change_type,
            classification.affected_modules,
            summary
        )
        self.save_metadata(metadata)
        
        logger.info(f"Iterative generation completed: {summary}")
        return self.working_dir
    
    def _extract_components_from_tree(
        self,
        module_tree: Dict[str, Any],
        all_components: Dict[str, Node]
    ) -> Dict[str, Node]:
        """
        Extract component nodes that exist in the module tree.
        
        Args:
            module_tree: The module tree
            all_components: All parsed components
            
        Returns:
            Dict of components that are in the module tree
        """
        tree_component_ids = set()
        
        def collect_ids(tree: Dict[str, Any]):
            for info in tree.values():
                tree_component_ids.update(info.get('components', []))
                children = info.get('children', {})
                if children:
                    collect_ids(children)
        
        collect_ids(module_tree)
        
        return {
            comp_id: comp 
            for comp_id, comp in all_components.items() 
            if comp_id in tree_component_ids
        }
    
    async def _handle_component_change(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node],
        from_commit: str
    ) -> List[UpdateResult]:
        """
        Handle component code changes without structural changes.
        
        Args:
            classification: The change classification
            module_tree: Current module tree
            components: All components
            from_commit: Starting commit for diffs
            
        Returns:
            List of UpdateResult from processing
        """
        logger.info("Handling component code changes")
        
        affected = classification.affected_components
        
        # Get git diffs for modified files
        git_diffs = self._collect_git_diffs(affected.modified_components, components, from_commit)
        
        # Create doc propagator
        propagator = DocPropagator(self.config, self.working_dir)
        
        # Find affected leaf modules
        affected_leaf_modules = propagator.find_affected_leaf_modules(
            module_tree, affected.modified_components
        )
        
        # Update each affected leaf module
        leaf_results = []
        for module_path in affected_leaf_modules:
            # Get components in this module that were affected
            module_info = self._get_module_at_path(module_tree, module_path)
            if not module_info:
                continue
            
            module_components = set(module_info.get('components', []))
            modified_in_module = [c for c in affected.modified_components if c in module_components]
            
            if modified_in_module:
                result = await propagator.update_leaf_module(
                    module_path=module_path,
                    module_tree=module_tree,
                    components=components,
                    modified_components=modified_in_module,
                    added_components=[],
                    deleted_components=[],
                    git_diffs=git_diffs
                )
                leaf_results.append(result)
        
        # Propagate to parents
        all_results = await propagator.propagate_updates(
            module_tree, leaf_results, components
        )
        
        return all_results
    
    async def _handle_minor_revision(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node],
        leaf_nodes: List[str],
        from_commit: str
    ) -> tuple[List[UpdateResult], Dict[str, Any]]:
        """
        Handle minor revisions (add/delete components).
        
        Args:
            classification: The change classification
            module_tree: Current module tree
            components: All components
            leaf_nodes: All leaf nodes
            from_commit: Starting commit for diffs
            
        Returns:
            Tuple of (UpdateResults, updated module tree)
        """
        logger.info("Handling minor revision (structural changes)")
        
        affected = classification.affected_components
        
        # Update module tree structure
        if affected.added_components:
            module_tree, added_to_modules = self.tree_updater.add_components_to_modules(
                module_tree, affected.added_components, components
            )
        else:
            added_to_modules = {}
        
        if affected.deleted_components:
            module_tree, removed_from_modules = self.tree_updater.remove_components_from_modules(
                module_tree, affected.deleted_components
            )
        else:
            removed_from_modules = {}
        
        # Get git diffs
        all_affected = affected.modified_components + affected.added_components
        git_diffs = self._collect_git_diffs(all_affected, components, from_commit)
        
        # Create doc propagator
        propagator = DocPropagator(self.config, self.working_dir)
        
        # Find all affected modules (from all types of changes)
        all_affected_modules = set()
        for module_path in classification.affected_modules:
            all_affected_modules.add(tuple(module_path))
        
        # Add modules that received new components
        for module_name in added_to_modules:
            # Find the path to this module
            paths = self._find_module_paths(module_tree, module_name)
            for path in paths:
                all_affected_modules.add(tuple(path))
        
        # Update each affected module
        leaf_results = []
        for module_path_tuple in all_affected_modules:
            module_path = list(module_path_tuple)
            module_name = module_path[-1]
            
            module_info = self._get_module_at_path(module_tree, module_path)
            if not module_info:
                continue
            
            # Check if this is a leaf module
            if module_info.get('children'):
                continue  # Skip non-leaf modules (they'll be updated via propagation)
            
            module_components = set(module_info.get('components', []))
            
            # Categorize affected components for this module
            modified_in_module = [c for c in affected.modified_components if c in module_components]
            added_in_module = [c for c in affected.added_components if c in module_components]
            deleted_from_module = removed_from_modules.get(module_name, [])
            
            if modified_in_module or added_in_module or deleted_from_module:
                result = await propagator.update_leaf_module(
                    module_path=module_path,
                    module_tree=module_tree,
                    components=components,
                    modified_components=modified_in_module,
                    added_components=added_in_module,
                    deleted_components=deleted_from_module,
                    git_diffs=git_diffs
                )
                leaf_results.append(result)
        
        # Propagate to parents
        all_results = await propagator.propagate_updates(
            module_tree, leaf_results, components
        )
        
        return all_results, module_tree
    
    async def _handle_major_revision(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node],
        leaf_nodes: List[str],
        from_commit: str
    ) -> tuple[List[UpdateResult], Dict[str, Any]]:
        """
        Handle major revisions requiring re-clustering.
        
        Args:
            classification: The change classification
            module_tree: Current module tree
            components: All components
            leaf_nodes: All leaf nodes
            from_commit: Starting commit for diffs
            
        Returns:
            Tuple of (UpdateResults, updated module tree)
        """
        logger.info("Handling major revision (re-clustering required)")
        
        # Determine which subtree needs re-clustering
        # For now, if change is major, we recluster the entire tree
        # In the future, we could be smarter about finding the minimal subtree
        
        affected = classification.affected_components
        
        # First, handle deletions
        if affected.deleted_components:
            module_tree, _ = self.tree_updater.remove_components_from_modules(
                module_tree, affected.deleted_components
            )
        
        # Re-cluster the affected area
        # Start with finding the common ancestor of all affected modules
        if classification.affected_modules:
            # Find common prefix
            common_path = self._find_common_ancestor(classification.affected_modules)
            module_tree = self.tree_updater.recluster_modules(
                module_tree, common_path, components, leaf_nodes
            )
        else:
            # No specific affected modules, recluster entire tree
            module_tree = self.tree_updater.recluster_modules(
                module_tree, [], components, leaf_nodes
            )
        
        # After re-clustering, regenerate documentation for affected modules
        propagator = DocPropagator(self.config, self.working_dir)
        
        # Find new leaf modules
        new_leaf_modules = self.tree_updater.find_leaf_modules(module_tree)
        
        # Generate documentation for modules that need it
        results = []
        for module_path in new_leaf_modules:
            module_name = module_path[-1]
            doc_path = os.path.join(self.working_dir, f"{module_name}.md")
            
            module_info = self._get_module_at_path(module_tree, module_path)
            if not module_info:
                continue
            
            module_components = module_info.get('components', [])
            
            if not os.path.exists(doc_path):
                # Generate new documentation
                logger.info(f"Generating new documentation for module: {module_name}")
                try:
                    await self.agent_orchestrator.process_module(
                        module_name, components, module_components, 
                        module_path, self.working_dir
                    )
                    results.append(UpdateResult(
                        module_path=module_path,
                        module_name=module_name,
                        success=True,
                        changes_summary="New module documentation generated"
                    ))
                except Exception as e:
                    logger.error(f"Failed to generate docs for {module_name}: {e}")
                    results.append(UpdateResult(
                        module_path=module_path,
                        module_name=module_name,
                        success=False,
                        error=str(e)
                    ))
        
        # Propagate updates to parents
        all_results = await propagator.propagate_updates(
            module_tree, results, components
        )
        
        return all_results, module_tree
    
    def _collect_git_diffs(
        self,
        component_ids: List[str],
        components: Dict[str, Node],
        from_commit: str
    ) -> Dict[str, str]:
        """
        Collect git diffs for files containing the specified components.
        
        Returns:
            Dict of file_path -> diff content
        """
        diffs = {}
        files_processed = set()
        
        for comp_id in component_ids:
            if comp_id not in components:
                continue
            
            file_path = components[comp_id].relative_path
            if file_path in files_processed:
                continue
            
            files_processed.add(file_path)
            diff = self.change_detector.get_file_diff(from_commit, file_path)
            if diff:
                diffs[file_path] = diff
        
        return diffs
    
    def _get_module_at_path(
        self,
        module_tree: Dict[str, Any],
        module_path: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get module info at the specified path."""
        current = module_tree
        for i, name in enumerate(module_path):
            if name not in current:
                return None
            if i == len(module_path) - 1:
                return current[name]
            current = current[name].get('children', {})
        return None
    
    def _find_module_paths(
        self,
        module_tree: Dict[str, Any],
        module_name: str
    ) -> List[List[str]]:
        """Find all paths to modules with the given name."""
        paths = []
        
        def search(tree: Dict[str, Any], current_path: List[str]):
            for name, info in tree.items():
                path = current_path + [name]
                if name == module_name:
                    paths.append(path)
                children = info.get('children', {})
                if children:
                    search(children, path)
        
        search(module_tree, [])
        return paths
    
    def _find_common_ancestor(self, module_paths: List[List[str]]) -> List[str]:
        """Find the common ancestor path of multiple module paths."""
        if not module_paths:
            return []
        
        if len(module_paths) == 1:
            return module_paths[0][:-1] if len(module_paths[0]) > 1 else []
        
        # Find common prefix
        common = []
        for i in range(min(len(p) for p in module_paths)):
            values = set(p[i] for p in module_paths)
            if len(values) == 1:
                common.append(module_paths[0][i])
            else:
                break
        
        return common
    
    def _create_update_summary(self, results: List[UpdateResult]) -> str:
        """Create a summary string from update results."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        parts = []
        if successful:
            parts.append(f"Updated {len(successful)} module(s)")
        if failed:
            parts.append(f"{len(failed)} update(s) failed")
        
        return "; ".join(parts) if parts else "No changes"
