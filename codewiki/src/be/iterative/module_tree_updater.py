"""
Module tree updater for iterative documentation generation.

This module handles modifications to the module tree structure,
including adding/removing components and re-clustering when needed.
"""

import logging
import os
from copy import deepcopy
from typing import Dict, List, Any, Optional, Tuple

from codewiki.src.config import Config
from codewiki.src.be.dependency_analyzer.models.core import Node
from codewiki.src.be.llm_services import call_llm
from codewiki.src.be.cluster_modules import cluster_modules
from codewiki.src.utils import file_manager

logger = logging.getLogger(__name__)


# Prompt for assigning new components to existing modules
ASSIGN_COMPONENTS_PROMPT = """
You are assigning new components to existing modules in a codebase.

## New Components to Assign:
{new_components_list}

## Existing Module Structure:
{module_tree}

## Task
For each new component, determine which existing module it belongs to.
Consider:
1. File path proximity (components in the same directory usually belong together)
2. Functional similarity (based on component names and types)
3. The existing module's purpose and scope

If a component clearly doesn't fit any existing module, suggest "NEW_MODULE" with a suggested name.

Output your assignments in the following format:
<ASSIGNMENTS>
{{
    "component_id_1": "existing_module_name",
    "component_id_2": "existing_module_name",
    "component_id_3": {{"new_module": "suggested_module_name", "reason": "explanation"}}
}}
</ASSIGNMENTS>
"""


class ModuleTreeUpdater:
    """Updates module tree structure based on changes."""
    
    def __init__(self, config: Config):
        """
        Initialize the module tree updater.
        
        Args:
            config: Configuration object
        """
        self.config = config
    
    def get_module_at_path(
        self,
        module_tree: Dict[str, Any],
        module_path: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get a module from the tree at the specified path.
        
        Args:
            module_tree: The module tree
            module_path: Path to the module (list of module names)
            
        Returns:
            The module info dict or None if not found
        """
        current = module_tree
        for i, name in enumerate(module_path):
            if name not in current:
                return None
            if i == len(module_path) - 1:
                return current[name]
            current = current[name].get('children', {})
        return None
    
    def set_module_at_path(
        self,
        module_tree: Dict[str, Any],
        module_path: List[str],
        module_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Set a module in the tree at the specified path.
        
        Args:
            module_tree: The module tree (will be modified)
            module_path: Path to the module
            module_info: The module info to set
            
        Returns:
            The modified module tree
        """
        if not module_path:
            return module_tree
            
        current = module_tree
        for i, name in enumerate(module_path[:-1]):
            if name not in current:
                current[name] = {'components': [], 'children': {}}
            current = current[name].setdefault('children', {})
        
        current[module_path[-1]] = module_info
        return module_tree
    
    def format_module_tree_for_prompt(self, module_tree: Dict[str, Any], indent: int = 0) -> str:
        """
        Format module tree as a readable string for prompts.
        
        Args:
            module_tree: The module tree
            indent: Current indentation level
            
        Returns:
            Formatted string representation
        """
        lines = []
        for name, info in module_tree.items():
            components = info.get('components', [])
            lines.append(f"{'  ' * indent}{name}")
            if components:
                lines.append(f"{'  ' * (indent + 1)}Components: {', '.join(components[:10])}")
                if len(components) > 10:
                    lines.append(f"{'  ' * (indent + 1)}... and {len(components) - 10} more")
            
            children = info.get('children', {})
            if children:
                lines.append(self.format_module_tree_for_prompt(children, indent + 1))
        
        return '\n'.join(lines)
    
    def add_components_to_modules(
        self,
        module_tree: Dict[str, Any],
        new_components: List[str],
        components: Dict[str, Node]
    ) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        """
        Add new components to appropriate existing modules.
        Uses LLM to determine best module placement.
        
        Args:
            module_tree: Current module tree
            new_components: List of new component IDs to add
            components: All components (including new ones)
            
        Returns:
            Tuple of (updated module tree, dict of module_name -> added components)
        """
        if not new_components:
            return module_tree, {}
        
        module_tree = deepcopy(module_tree)
        added_to_modules: Dict[str, List[str]] = {}
        
        # Format new components for the prompt
        new_components_info = []
        for comp_id in new_components:
            if comp_id in components:
                comp = components[comp_id]
                new_components_info.append(
                    f"- {comp_id} (type: {comp.component_type}, file: {comp.relative_path})"
                )
        
        if not new_components_info:
            return module_tree, {}
        
        # Create prompt for LLM
        prompt = ASSIGN_COMPONENTS_PROMPT.format(
            new_components_list='\n'.join(new_components_info),
            module_tree=self.format_module_tree_for_prompt(module_tree)
        )
        
        try:
            response = call_llm(prompt, self.config)
            
            # Parse assignments from response
            if '<ASSIGNMENTS>' in response and '</ASSIGNMENTS>' in response:
                assignments_str = response.split('<ASSIGNMENTS>')[1].split('</ASSIGNMENTS>')[0]
                assignments = eval(assignments_str.strip())
                
                # Apply assignments
                for comp_id, assignment in assignments.items():
                    if comp_id not in new_components:
                        continue
                    
                    if isinstance(assignment, str):
                        # Assign to existing module
                        module_name = assignment
                        self._add_component_to_module(module_tree, module_name, comp_id)
                        added_to_modules.setdefault(module_name, []).append(comp_id)
                    elif isinstance(assignment, dict) and 'new_module' in assignment:
                        # Create new module
                        new_module_name = assignment['new_module']
                        module_tree[new_module_name] = {
                            'components': [comp_id],
                            'children': {}
                        }
                        added_to_modules.setdefault(new_module_name, []).append(comp_id)
                        logger.info(f"Created new module '{new_module_name}' for component {comp_id}")
                
        except Exception as e:
            logger.error(f"Failed to assign components via LLM: {e}")
            # Fallback: assign based on file path similarity
            added_to_modules = self._assign_by_file_path(module_tree, new_components, components)
        
        logger.info(f"Added {len(new_components)} components to modules: {added_to_modules}")
        return module_tree, added_to_modules
    
    def _add_component_to_module(
        self,
        module_tree: Dict[str, Any],
        module_name: str,
        component_id: str
    ) -> bool:
        """
        Add a component to a module (searches recursively).
        
        Returns:
            True if component was added, False if module not found
        """
        def search_and_add(tree: Dict[str, Any]) -> bool:
            for name, info in tree.items():
                if name == module_name:
                    if 'components' not in info:
                        info['components'] = []
                    info['components'].append(component_id)
                    return True
                
                children = info.get('children', {})
                if children and search_and_add(children):
                    return True
            return False
        
        return search_and_add(module_tree)
    
    def _assign_by_file_path(
        self,
        module_tree: Dict[str, Any],
        new_components: List[str],
        components: Dict[str, Node]
    ) -> Dict[str, List[str]]:
        """
        Fallback: assign components to modules based on file path similarity.
        
        Returns:
            Dict of module_name -> added components
        """
        added_to_modules: Dict[str, List[str]] = {}
        
        # Build map of directory prefixes to modules
        dir_to_module: Dict[str, str] = {}
        
        def map_dirs(tree: Dict[str, Any], prefix: str = ""):
            for name, info in tree.items():
                module_components = info.get('components', [])
                for comp_id in module_components:
                    if comp_id in components:
                        comp_dir = os.path.dirname(components[comp_id].relative_path)
                        if comp_dir:
                            dir_to_module[comp_dir] = name
                
                children = info.get('children', {})
                if children:
                    map_dirs(children, prefix)
        
        map_dirs(module_tree)
        
        # Assign new components based on their directory
        for comp_id in new_components:
            if comp_id not in components:
                continue
            
            comp_dir = os.path.dirname(components[comp_id].relative_path)
            
            # Try to find matching module
            assigned = False
            while comp_dir:
                if comp_dir in dir_to_module:
                    module_name = dir_to_module[comp_dir]
                    self._add_component_to_module(module_tree, module_name, comp_id)
                    added_to_modules.setdefault(module_name, []).append(comp_id)
                    assigned = True
                    break
                comp_dir = os.path.dirname(comp_dir)
            
            # If no match found, add to first top-level module
            if not assigned and module_tree:
                first_module = list(module_tree.keys())[0]
                self._add_component_to_module(module_tree, first_module, comp_id)
                added_to_modules.setdefault(first_module, []).append(comp_id)
        
        return added_to_modules
    
    def remove_components_from_modules(
        self,
        module_tree: Dict[str, Any],
        deleted_components: List[str]
    ) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        """
        Remove deleted components from modules.
        Cleans up empty modules if necessary.
        
        Args:
            module_tree: Current module tree
            deleted_components: List of component IDs to remove
            
        Returns:
            Tuple of (updated module tree, dict of module_name -> removed components)
        """
        if not deleted_components:
            return module_tree, {}
        
        module_tree = deepcopy(module_tree)
        deleted_set = set(deleted_components)
        removed_from_modules: Dict[str, List[str]] = {}
        
        def remove_from_tree(tree: Dict[str, Any]) -> List[str]:
            """Remove components and return list of modules that became empty."""
            empty_modules = []
            
            for name, info in list(tree.items()):
                components = info.get('components', [])
                
                # Remove deleted components
                original_count = len(components)
                remaining = [c for c in components if c not in deleted_set]
                removed = [c for c in components if c in deleted_set]
                
                if removed:
                    info['components'] = remaining
                    removed_from_modules[name] = removed
                    logger.debug(f"Removed {len(removed)} components from module '{name}'")
                
                # Recursively process children
                children = info.get('children', {})
                if children:
                    empty_children = remove_from_tree(children)
                    # Remove empty child modules
                    for empty_child in empty_children:
                        del children[empty_child]
                
                # Check if module is now empty (no components and no children)
                if not info.get('components') and not info.get('children'):
                    empty_modules.append(name)
            
            return empty_modules
        
        empty_modules = remove_from_tree(module_tree)
        
        # Remove top-level empty modules
        for empty_name in empty_modules:
            if empty_name in module_tree:
                del module_tree[empty_name]
                logger.info(f"Removed empty module: {empty_name}")
        
        logger.info(f"Removed {len(deleted_components)} components from modules")
        return module_tree, removed_from_modules
    
    def recluster_modules(
        self,
        module_tree: Dict[str, Any],
        affected_subtree_path: List[str],
        components: Dict[str, Node],
        leaf_nodes: List[str]
    ) -> Dict[str, Any]:
        """
        Re-cluster a subtree of the module tree.
        Used for major revisions.
        
        Args:
            module_tree: Current module tree
            affected_subtree_path: Path to the subtree root to recluster
                                   Empty list means recluster entire tree
            components: All components
            leaf_nodes: All leaf nodes
            
        Returns:
            Updated module tree with reclustered subtree
        """
        module_tree = deepcopy(module_tree)
        
        if not affected_subtree_path:
            # Recluster entire tree
            logger.info("Re-clustering entire module tree")
            new_tree = cluster_modules(leaf_nodes, components, self.config)
            return new_tree if new_tree else module_tree
        
        # Get the subtree to recluster
        subtree_module = self.get_module_at_path(module_tree, affected_subtree_path)
        if not subtree_module:
            logger.warning(f"Subtree not found at path: {affected_subtree_path}")
            return module_tree
        
        # Get all components under this subtree
        subtree_components = self._collect_subtree_components(subtree_module)
        subtree_leaf_nodes = [c for c in subtree_components if c in leaf_nodes]
        
        if not subtree_leaf_nodes:
            logger.warning("No leaf nodes in subtree to recluster")
            return module_tree
        
        # Recluster this subtree
        logger.info(f"Re-clustering subtree at {'/'.join(affected_subtree_path)} with {len(subtree_leaf_nodes)} leaf nodes")
        
        # Get parent tree for context
        parent_path = affected_subtree_path[:-1]
        parent_tree = {}
        if parent_path:
            parent_module = self.get_module_at_path(module_tree, parent_path)
            if parent_module:
                parent_tree = parent_module.get('children', {})
        else:
            parent_tree = {k: v for k, v in module_tree.items() if k != affected_subtree_path[0]}
        
        new_subtree = cluster_modules(
            subtree_leaf_nodes,
            components,
            self.config,
            current_module_tree=parent_tree,
            current_module_name=affected_subtree_path[-1],
            current_module_path=affected_subtree_path[:-1]
        )
        
        if new_subtree:
            # Replace the old subtree with the new one
            if len(affected_subtree_path) == 1:
                # Top-level module
                module_tree[affected_subtree_path[0]] = {
                    'components': subtree_module.get('components', []),
                    'children': new_subtree
                }
            else:
                # Nested module
                parent = self.get_module_at_path(module_tree, affected_subtree_path[:-1])
                if parent and 'children' in parent:
                    parent['children'][affected_subtree_path[-1]] = {
                        'components': subtree_module.get('components', []),
                        'children': new_subtree
                    }
        
        return module_tree
    
    def _collect_subtree_components(self, module_info: Dict[str, Any]) -> List[str]:
        """
        Collect all component IDs from a module subtree.
        
        Args:
            module_info: The module info dict
            
        Returns:
            List of all component IDs in the subtree
        """
        components = list(module_info.get('components', []))
        
        children = module_info.get('children', {})
        for child_info in children.values():
            components.extend(self._collect_subtree_components(child_info))
        
        return components
    
    def find_leaf_modules(self, module_tree: Dict[str, Any]) -> List[List[str]]:
        """
        Find all leaf modules (modules with no children).
        
        Args:
            module_tree: The module tree
            
        Returns:
            List of module paths for all leaf modules
        """
        leaf_modules = []
        
        def find_leaves(tree: Dict[str, Any], current_path: List[str]):
            for name, info in tree.items():
                module_path = current_path + [name]
                children = info.get('children', {})
                
                if not children:
                    leaf_modules.append(module_path)
                else:
                    find_leaves(children, module_path)
        
        find_leaves(module_tree, [])
        return leaf_modules
