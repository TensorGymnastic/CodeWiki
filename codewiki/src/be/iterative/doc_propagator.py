"""
Documentation propagator for iterative documentation generation.

This module handles recursive propagation of documentation updates
through the module tree hierarchy.
"""

import logging
import os
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

from pydantic_ai import Agent

from codewiki.src.config import Config
from codewiki.src.be.dependency_analyzer.models.core import Node
from codewiki.src.be.llm_services import call_llm, create_fallback_models
from codewiki.src.be.agent_tools.deps import CodeWikiDeps
from codewiki.src.be.agent_tools.read_code_components import read_code_components_tool
from codewiki.src.be.agent_tools.str_replace_editor import str_replace_editor_tool
from codewiki.src.utils import file_manager

logger = logging.getLogger(__name__)


# System prompt for updating leaf module documentation
UPDATE_LEAF_MODULE_SYSTEM_PROMPT = """
<ROLE>
You are an AI documentation assistant. Your task is to UPDATE existing documentation for a module based on code changes.
</ROLE>

<OBJECTIVES>
Update the documentation to reflect recent code changes while:
1. Preserving the existing documentation structure and style
2. Updating descriptions of modified components
3. Adding documentation for new components (if any)
4. Removing references to deleted components (if any)
5. Updating diagrams if component relationships changed
</OBJECTIVES>

<WORKFLOW>
1. Review the changes summary and affected components
2. Read the current documentation
3. Read the updated code for affected components
4. Make targeted updates to the documentation using str_replace_editor
5. Ensure Mermaid diagrams are updated if needed
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: View and edit documentation files
- `read_code_components`: Read updated code for components
</AVAILABLE_TOOLS>

<IMPORTANT>
- Make MINIMAL changes - only update what's necessary
- Preserve the documentation style and formatting
- Do NOT regenerate the entire documentation
- Focus on the affected areas only
</IMPORTANT>
{custom_instructions}
""".strip()


UPDATE_LEAF_MODULE_USER_PROMPT = """
Update the documentation for module: {module_name}

## Changes Summary
{changes_summary}

## Affected Components

### Modified Components:
{modified_components}

### Added Components (document these):
{added_components}

### Deleted Components (remove references):
{deleted_components}

## Git Diff for Modified Files
{git_diff}

## Current Documentation
The documentation file is at: {doc_file_path}

Please update the documentation to reflect these changes. Use the tools to:
1. View the current documentation
2. Read the updated code for modified/added components
3. Make targeted edits to update the documentation

Output a brief summary of changes made at the end.
""".strip()


# Prompt for updating parent module documentation
UPDATE_PARENT_MODULE_PROMPT = """
You are updating the parent module documentation: {module_name}

## Child Modules That Were Updated

{child_updates_summary}

## Current Parent Documentation
{current_parent_documentation}

## Task
Update the parent module documentation to reflect changes in child modules.
Focus on:
1. Updating the module overview if child functionality changed significantly
2. Updating cross-module interaction descriptions
3. Updating diagrams showing module relationships
4. Ensuring the parent accurately summarizes child modules

Keep changes MINIMAL - only update what's necessary based on child changes.

Output the updated documentation in the following format:
<UPDATED_DOCUMENTATION>
updated content here
</UPDATED_DOCUMENTATION>

Also output a brief summary of what was changed:
<CHANGES_SUMMARY>
summary here
</CHANGES_SUMMARY>
"""


@dataclass
class UpdateResult:
    """Result of a documentation update."""
    module_path: List[str]
    module_name: str
    success: bool
    changes_summary: str = ""
    error: Optional[str] = None


class DocPropagator:
    """Propagates documentation changes through the module tree."""
    
    def __init__(self, config: Config, working_dir: str):
        """
        Initialize the documentation propagator.
        
        Args:
            config: Configuration object
            working_dir: Working directory for documentation files
        """
        self.config = config
        self.working_dir = working_dir
        self._update_stack: Set[str] = set()  # Prevents infinite loops
        self._max_propagation_depth: int = getattr(config, 'max_propagation_depth', 10)
        self._current_depth: int = 0
        self.custom_instructions = config.get_prompt_addition() if config else ""
        self.fallback_models = create_fallback_models(config)
    
    def _module_path_to_key(self, module_path: List[str]) -> str:
        """Convert module path to a string key."""
        return "/".join(module_path)
    
    def find_affected_leaf_modules(
        self,
        module_tree: Dict[str, Any],
        affected_components: List[str]
    ) -> List[List[str]]:
        """
        Find leaf modules containing affected components.
        
        Args:
            module_tree: The module tree
            affected_components: List of affected component IDs
            
        Returns:
            List of module paths for affected leaf modules
        """
        affected_set = set(affected_components)
        affected_modules = []
        
        def find_in_tree(tree: Dict[str, Any], current_path: List[str]):
            for name, info in tree.items():
                module_path = current_path + [name]
                children = info.get('children', {})
                
                # Check if this is a leaf module
                if not children:
                    # Check if any affected components are in this module
                    module_components = set(info.get('components', []))
                    if module_components & affected_set:
                        affected_modules.append(module_path)
                else:
                    # Recurse into children
                    find_in_tree(children, module_path)
        
        find_in_tree(module_tree, [])
        return affected_modules
    
    def get_parent_module_path(self, module_path: List[str]) -> Optional[List[str]]:
        """
        Get the parent module path.
        
        Args:
            module_path: Current module path
            
        Returns:
            Parent module path or None if at root
        """
        if len(module_path) <= 1:
            return None
        return module_path[:-1]
    
    def get_module_doc_path(self, module_name: str) -> str:
        """Get the documentation file path for a module."""
        return os.path.join(self.working_dir, f"{module_name}.md")
    
    def load_module_doc(self, module_name: str) -> Optional[str]:
        """Load documentation content for a module."""
        doc_path = self.get_module_doc_path(module_name)
        if os.path.exists(doc_path):
            return file_manager.load_text(doc_path)
        return None
    
    def save_module_doc(self, module_name: str, content: str) -> None:
        """Save documentation content for a module."""
        doc_path = self.get_module_doc_path(module_name)
        file_manager.save_text(content, doc_path)
    
    async def update_leaf_module(
        self,
        module_path: List[str],
        module_tree: Dict[str, Any],
        components: Dict[str, Node],
        modified_components: List[str],
        added_components: List[str],
        deleted_components: List[str],
        git_diffs: Dict[str, str]
    ) -> UpdateResult:
        """
        Update documentation for a leaf module.
        
        Args:
            module_path: Path to the module
            module_tree: The module tree
            components: All components
            modified_components: List of modified component IDs in this module
            added_components: List of added component IDs in this module
            deleted_components: List of deleted component IDs from this module
            git_diffs: Dict of file_path -> diff content
            
        Returns:
            UpdateResult with status and changes summary
        """
        module_name = module_path[-1]
        module_key = self._module_path_to_key(module_path)
        
        logger.info(f"Updating leaf module documentation: {module_name}")
        
        # Check if already being updated (cycle prevention)
        if module_key in self._update_stack:
            logger.warning(f"Cycle detected, skipping: {module_key}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error="Cycle detected"
            )
        
        # Check if doc exists
        doc_path = self.get_module_doc_path(module_name)
        if not os.path.exists(doc_path):
            logger.warning(f"Documentation not found for module: {module_name}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error="Documentation file not found"
            )
        
        self._update_stack.add(module_key)
        
        try:
            # Format component lists for the prompt
            modified_list = "\n".join([f"- {c}" for c in modified_components]) or "None"
            added_list = "\n".join([f"- {c}" for c in added_components]) or "None"
            deleted_list = "\n".join([f"- {c}" for c in deleted_components]) or "None"
            
            # Collect relevant diffs
            relevant_diffs = []
            all_affected = modified_components + added_components
            for comp_id in all_affected:
                if comp_id in components:
                    file_path = components[comp_id].relative_path
                    if file_path in git_diffs:
                        relevant_diffs.append(f"### {file_path}\n```diff\n{git_diffs[file_path]}\n```")
            
            diff_content = "\n\n".join(relevant_diffs) if relevant_diffs else "No diffs available"
            
            # Create changes summary
            changes_summary = []
            if modified_components:
                changes_summary.append(f"- {len(modified_components)} component(s) modified")
            if added_components:
                changes_summary.append(f"- {len(added_components)} component(s) added")
            if deleted_components:
                changes_summary.append(f"- {len(deleted_components)} component(s) deleted")
            
            # Create agent for updating documentation
            custom_section = ""
            if self.custom_instructions:
                custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{self.custom_instructions}\n</CUSTOM_INSTRUCTIONS>"
            
            agent = Agent(
                self.fallback_models,
                name=f"update_{module_name}",
                deps_type=CodeWikiDeps,
                tools=[read_code_components_tool, str_replace_editor_tool],
                system_prompt=UPDATE_LEAF_MODULE_SYSTEM_PROMPT.format(
                    custom_instructions=custom_section
                ),
            )
            
            # Get module info from tree
            module_info = self._get_module_at_path(module_tree, module_path)
            
            # Create dependencies
            deps = CodeWikiDeps(
                absolute_docs_path=self.working_dir,
                absolute_repo_path=str(os.path.abspath(self.config.repo_path)),
                registry={},
                components=components,
                path_to_current_module=module_path,
                current_module_name=module_name,
                module_tree=module_tree,
                max_depth=self.config.max_depth,
                current_depth=1,
                config=self.config,
                custom_instructions=self.custom_instructions
            )
            
            # Format user prompt
            user_prompt = UPDATE_LEAF_MODULE_USER_PROMPT.format(
                module_name=module_name,
                changes_summary="\n".join(changes_summary),
                modified_components=modified_list,
                added_components=added_list,
                deleted_components=deleted_list,
                git_diff=diff_content,
                doc_file_path=f"{module_name}.md"
            )
            
            # Run agent
            result = await agent.run(user_prompt, deps=deps)
            
            # Extract changes summary from result
            result_text = str(result.data) if result.data else ""
            
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=True,
                changes_summary=result_text[-500:] if len(result_text) > 500 else result_text
            )
            
        except Exception as e:
            logger.error(f"Failed to update module {module_name}: {e}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error=str(e)
            )
        finally:
            self._update_stack.discard(module_key)
    
    async def update_parent_module(
        self,
        module_path: List[str],
        child_updates: List[UpdateResult]
    ) -> UpdateResult:
        """
        Update documentation for a parent module based on child updates.
        
        Args:
            module_path: Path to the parent module
            child_updates: List of UpdateResult from child modules
            
        Returns:
            UpdateResult with status and changes summary
        """
        module_name = module_path[-1] if module_path else os.path.basename(self.config.repo_path)
        module_key = self._module_path_to_key(module_path) if module_path else "root"
        
        logger.info(f"Updating parent module documentation: {module_name}")
        
        # Check depth limit
        if self._current_depth >= self._max_propagation_depth:
            logger.warning(f"Max propagation depth reached: {module_name}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error="Max propagation depth reached"
            )
        
        # Check for cycles
        if module_key in self._update_stack:
            logger.warning(f"Cycle detected, skipping: {module_key}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error="Cycle detected"
            )
        
        # Load current documentation
        doc_name = module_name if module_path else "overview"
        current_doc = self.load_module_doc(doc_name)
        if not current_doc:
            logger.warning(f"Parent documentation not found: {doc_name}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error="Documentation file not found"
            )
        
        self._update_stack.add(module_key)
        self._current_depth += 1
        
        try:
            # Format child updates summary
            child_summaries = []
            for update in child_updates:
                if update.success and update.changes_summary:
                    child_summaries.append(
                        f"### {update.module_name}\n{update.changes_summary}"
                    )
            
            if not child_summaries:
                # No meaningful child updates to propagate
                return UpdateResult(
                    module_path=module_path,
                    module_name=module_name,
                    success=True,
                    changes_summary="No changes needed - child updates were minor"
                )
            
            # Create prompt for LLM
            prompt = UPDATE_PARENT_MODULE_PROMPT.format(
                module_name=module_name,
                child_updates_summary="\n\n".join(child_summaries),
                current_parent_documentation=current_doc
            )
            
            # Call LLM
            response = call_llm(prompt, self.config)
            
            # Parse response
            if '<UPDATED_DOCUMENTATION>' in response and '</UPDATED_DOCUMENTATION>' in response:
                updated_doc = response.split('<UPDATED_DOCUMENTATION>')[1].split('</UPDATED_DOCUMENTATION>')[0].strip()
                self.save_module_doc(doc_name, updated_doc)
            
            changes_summary = ""
            if '<CHANGES_SUMMARY>' in response and '</CHANGES_SUMMARY>' in response:
                changes_summary = response.split('<CHANGES_SUMMARY>')[1].split('</CHANGES_SUMMARY>')[0].strip()
            
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=True,
                changes_summary=changes_summary
            )
            
        except Exception as e:
            logger.error(f"Failed to update parent module {module_name}: {e}")
            return UpdateResult(
                module_path=module_path,
                module_name=module_name,
                success=False,
                error=str(e)
            )
        finally:
            self._update_stack.discard(module_key)
            self._current_depth -= 1
    
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
    
    async def propagate_updates(
        self,
        module_tree: Dict[str, Any],
        leaf_updates: List[UpdateResult],
        components: Dict[str, Node]
    ) -> List[UpdateResult]:
        """
        Recursively propagate documentation updates from leaves to root.
        
        Args:
            module_tree: The module tree
            leaf_updates: Updates from leaf modules
            components: All components
            
        Returns:
            List of all UpdateResults including parent updates
        """
        all_results = list(leaf_updates)
        
        # Group updates by parent
        parent_to_children: Dict[str, List[UpdateResult]] = {}
        
        for update in leaf_updates:
            if not update.success:
                continue
                
            parent_path = self.get_parent_module_path(update.module_path)
            if parent_path:
                parent_key = self._module_path_to_key(parent_path)
                parent_to_children.setdefault(parent_key, []).append(update)
        
        # Process each parent level
        current_level_updates = leaf_updates
        
        while parent_to_children:
            next_level_parents: Dict[str, List[UpdateResult]] = {}
            
            for parent_key, child_updates in parent_to_children.items():
                parent_path = parent_key.split("/") if parent_key else []
                
                # Update parent
                parent_result = await self.update_parent_module(parent_path, child_updates)
                all_results.append(parent_result)
                
                # Queue grandparent for next iteration
                if parent_result.success:
                    grandparent_path = self.get_parent_module_path(parent_path)
                    if grandparent_path:
                        grandparent_key = self._module_path_to_key(grandparent_path)
                        next_level_parents.setdefault(grandparent_key, []).append(parent_result)
                    elif parent_path:
                        # This was a top-level module, update root overview
                        root_key = ""
                        next_level_parents.setdefault(root_key, []).append(parent_result)
            
            parent_to_children = next_level_parents
        
        return all_results
