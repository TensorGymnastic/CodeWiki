"""
Change detection module for iterative documentation generation.

This module analyzes git changes between commits and classifies them
into categories that determine the documentation update strategy.
"""

import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum

from codewiki.src.config import Config
from codewiki.src.be.dependency_analyzer.models.core import Node

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes that can occur."""
    COMPONENT_CHANGE = "component_change"  # Only existing components modified
    MINOR_REVISION = "minor_revision"      # Components added/deleted in existing modules
    MAJOR_REVISION = "major_revision"      # Significant structural changes


@dataclass
class AffectedComponents:
    """Container for components affected by changes."""
    modified_components: List[str] = field(default_factory=list)  # Component IDs with code changes
    added_components: List[str] = field(default_factory=list)     # New component IDs
    deleted_components: List[str] = field(default_factory=list)   # Removed component IDs
    
    @property
    def has_structural_changes(self) -> bool:
        """Check if there are structural changes (additions/deletions)."""
        return bool(self.added_components or self.deleted_components)
    
    @property
    def total_affected(self) -> int:
        """Get total number of affected components."""
        return len(self.modified_components) + len(self.added_components) + len(self.deleted_components)


@dataclass
class ChangeClassification:
    """Classification result for detected changes."""
    change_type: ChangeType
    affected_modules: List[List[str]] = field(default_factory=list)  # List of module paths
    affected_components: AffectedComponents = field(default_factory=AffectedComponents)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_component_change(self) -> bool:
        return self.change_type == ChangeType.COMPONENT_CHANGE
    
    @property
    def is_minor_revision(self) -> bool:
        return self.change_type == ChangeType.MINOR_REVISION
    
    @property
    def is_major_revision(self) -> bool:
        return self.change_type == ChangeType.MAJOR_REVISION


class ChangeDetector:
    """Detects and classifies changes between commits."""
    
    def __init__(self, repo_path: str, config: Config):
        """
        Initialize the change detector.
        
        Args:
            repo_path: Path to the git repository
            config: Configuration object
        """
        self.repo_path = repo_path
        self.config = config
        # Threshold for major revision (percentage of components changed)
        self.major_revision_threshold = getattr(config, 'major_revision_threshold', 0.3)
    
    def is_commit_valid(self, commit_id: str) -> bool:
        """
        Check if a commit exists in the git history.
        
        Args:
            commit_id: The commit hash to check
            
        Returns:
            True if commit exists, False otherwise
        """
        try:
            result = subprocess.run(
                ['git', 'cat-file', '-t', commit_id],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0 and 'commit' in result.stdout
        except Exception as e:
            logger.warning(f"Failed to check commit validity: {e}")
            return False
    
    def get_current_commit(self) -> Optional[str]:
        """
        Get the current HEAD commit hash.
        
        Returns:
            Current commit hash or None if failed
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.error(f"Failed to get current commit: {e}")
            return None
    
    def get_changed_files(self, from_commit: str, to_commit: str = "HEAD") -> Dict[str, str]:
        """
        Get files changed between commits.
        
        Args:
            from_commit: Starting commit hash
            to_commit: Ending commit hash (default: HEAD)
            
        Returns:
            Dict mapping file_path -> change_type ('A', 'M', 'D', 'R')
        """
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-status', from_commit, to_commit],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Git diff failed: {result.stderr}")
                return {}
            
            changed_files = {}
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0][0]  # First character is the status
                    file_path = parts[-1]  # Last part is the file path (handles renames)
                    
                    # For renames, also track the old path as deleted
                    if status == 'R' and len(parts) == 3:
                        old_path = parts[1]
                        changed_files[old_path] = 'D'
                        changed_files[file_path] = 'A'
                    else:
                        changed_files[file_path] = status
            
            logger.info(f"Found {len(changed_files)} changed files between {from_commit[:8]} and {to_commit[:8] if to_commit != 'HEAD' else 'HEAD'}")
            return changed_files
            
        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            return {}
    
    def get_file_diff(self, from_commit: str, file_path: str, to_commit: str = "HEAD") -> str:
        """
        Get the diff content for a specific file.
        
        Args:
            from_commit: Starting commit hash
            file_path: Path to the file
            to_commit: Ending commit hash (default: HEAD)
            
        Returns:
            Diff content as string
        """
        try:
            result = subprocess.run(
                ['git', 'diff', from_commit, to_commit, '--', file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            logger.error(f"Failed to get file diff: {e}")
            return ""
    
    def extract_affected_components(
        self, 
        changed_files: Dict[str, str],
        existing_components: Dict[str, Node],
        new_components: Optional[Dict[str, Node]] = None
    ) -> AffectedComponents:
        """
        Parse changed files and extract affected components.
        
        Args:
            changed_files: Dict mapping file_path -> change_type
            existing_components: Current components from module tree
            new_components: Newly parsed components (if available)
            
        Returns:
            AffectedComponents containing modified, added, and deleted components
        """
        affected = AffectedComponents()
        
        # Build a map of file paths to component IDs from existing components
        file_to_components: Dict[str, List[str]] = {}
        for comp_id, comp in existing_components.items():
            rel_path = comp.relative_path
            if rel_path not in file_to_components:
                file_to_components[rel_path] = []
            file_to_components[rel_path].append(comp_id)
        
        # Build a map for new components if provided
        new_file_to_components: Dict[str, List[str]] = {}
        if new_components:
            for comp_id, comp in new_components.items():
                rel_path = comp.relative_path
                if rel_path not in new_file_to_components:
                    new_file_to_components[rel_path] = []
                new_file_to_components[rel_path].append(comp_id)
        
        for file_path, change_type in changed_files.items():
            if change_type == 'D':
                # Deleted file - all components in it are deleted
                if file_path in file_to_components:
                    affected.deleted_components.extend(file_to_components[file_path])
                    
            elif change_type == 'A':
                # Added file - all components in it are new
                if new_components and file_path in new_file_to_components:
                    affected.added_components.extend(new_file_to_components[file_path])
                    
            elif change_type == 'M':
                # Modified file - need to determine which components changed
                old_components = set(file_to_components.get(file_path, []))
                new_comps = set(new_file_to_components.get(file_path, [])) if new_components else old_components
                
                # Components that exist in both - modified
                modified = old_components & new_comps
                affected.modified_components.extend(modified)
                
                # Components only in old - deleted
                deleted = old_components - new_comps
                affected.deleted_components.extend(deleted)
                
                # Components only in new - added
                added = new_comps - old_components
                affected.added_components.extend(added)
        
        logger.info(
            f"Affected components: {len(affected.modified_components)} modified, "
            f"{len(affected.added_components)} added, {len(affected.deleted_components)} deleted"
        )
        
        return affected
    
    def find_component_modules(
        self,
        component_ids: List[str],
        module_tree: Dict[str, Any]
    ) -> List[List[str]]:
        """
        Find which modules contain the given components.
        
        Args:
            component_ids: List of component IDs to find
            module_tree: The module tree structure
            
        Returns:
            List of module paths (each path is a list of module names)
        """
        component_set = set(component_ids)
        affected_modules: List[List[str]] = []
        
        def search_tree(tree: Dict[str, Any], current_path: List[str]):
            for module_name, module_info in tree.items():
                module_path = current_path + [module_name]
                
                # Check if this module contains any of the components
                module_components = set(module_info.get('components', []))
                if module_components & component_set:
                    affected_modules.append(module_path)
                
                # Recurse into children
                children = module_info.get('children', {})
                if children:
                    search_tree(children, module_path)
        
        search_tree(module_tree, [])
        return affected_modules
    
    def classify_changes(
        self,
        affected: AffectedComponents,
        module_tree: Dict[str, Any],
        total_components: int
    ) -> ChangeClassification:
        """
        Classify the type of change required.
        
        Args:
            affected: The affected components
            module_tree: Current module tree structure
            total_components: Total number of components in the codebase
            
        Returns:
            ChangeClassification with change type and affected modules
        """
        # Find affected modules
        all_affected_component_ids = (
            affected.modified_components + 
            affected.added_components + 
            affected.deleted_components
        )
        
        # For modified/deleted, find their current modules
        existing_affected = affected.modified_components + affected.deleted_components
        affected_modules = self.find_component_modules(existing_affected, module_tree)
        
        # Calculate change ratio
        change_ratio = affected.total_affected / max(total_components, 1)
        
        # Determine change type
        if change_ratio >= self.major_revision_threshold:
            # Major revision - significant portion of codebase changed
            change_type = ChangeType.MAJOR_REVISION
            details = {
                'reason': 'change_ratio_exceeded',
                'change_ratio': change_ratio,
                'threshold': self.major_revision_threshold
            }
        elif affected.has_structural_changes:
            # Minor revision - structural changes but not too many
            change_type = ChangeType.MINOR_REVISION
            details = {
                'reason': 'structural_changes',
                'added_count': len(affected.added_components),
                'deleted_count': len(affected.deleted_components)
            }
        else:
            # Component change - only modifications to existing components
            change_type = ChangeType.COMPONENT_CHANGE
            details = {
                'reason': 'modifications_only',
                'modified_count': len(affected.modified_components)
            }
        
        classification = ChangeClassification(
            change_type=change_type,
            affected_modules=affected_modules,
            affected_components=affected,
            details=details
        )
        
        logger.info(f"Change classification: {change_type.value} - {details}")
        
        return classification
    
    def detect_changes(
        self,
        from_commit: str,
        existing_components: Dict[str, Node],
        new_components: Optional[Dict[str, Node]],
        module_tree: Dict[str, Any],
        to_commit: str = "HEAD"
    ) -> Optional[ChangeClassification]:
        """
        Full change detection pipeline.
        
        Args:
            from_commit: Starting commit hash
            existing_components: Components from the previous generation
            new_components: Newly parsed components
            module_tree: Current module tree
            to_commit: Ending commit hash (default: HEAD)
            
        Returns:
            ChangeClassification or None if no changes
        """
        # Validate from_commit
        if not self.is_commit_valid(from_commit):
            logger.error(f"Invalid from_commit: {from_commit}")
            return None
        
        # Get changed files
        changed_files = self.get_changed_files(from_commit, to_commit)
        if not changed_files:
            logger.info("No changes detected")
            return None
        
        # Extract affected components
        affected = self.extract_affected_components(
            changed_files, existing_components, new_components
        )
        
        if affected.total_affected == 0:
            logger.info("No component changes detected (only non-code files changed)")
            return None
        
        # Classify changes
        total_components = len(new_components) if new_components else len(existing_components)
        classification = self.classify_changes(affected, module_tree, total_components)
        
        return classification
