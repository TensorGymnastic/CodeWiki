# Iterative Documentation Generation

## Overview

This document describes the design for iterative documentation generation in CodeWiki. Instead of regenerating documentation from scratch for every change, this feature enables incremental updates based on git commits since the last documentation generation.

## Motivation

Full documentation generation for large codebases is:
- **Time-consuming**: Processing all components takes significant LLM calls
- **Costly**: Each generation requires many API calls
- **Redundant**: Most changes affect only a small portion of the codebase

Iterative generation solves these problems by:
1. Storing the commit hash when documentation is generated
2. Detecting changes since the last stored hash
3. Intelligently updating only affected documentation

## Key Concepts

### Commit Hash Tracking

The commit hash is already stored in `metadata.json`:

```json
{
  "generation_info": {
    "timestamp": "2025-01-19T10:00:00",
    "commit_id": "abc123def456...",
    ...
  }
}
```

### Change Categories

Changes are classified into three categories based on their impact:

| Category | Description | Module Tree Impact | Documentation Impact |
|----------|-------------|-------------------|---------------------|
| **Component Code Change** | Existing components modified | No structural change | Update affected leaf docs + propagate |
| **Minor Revision** | Components added/deleted within existing modules | Add/remove components | Update affected modules + propagate |
| **Major Revision** | Significant structural changes requiring re-clustering | Re-cluster modules | Regenerate affected module subtrees |

### Change Detection Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                     Git Diff Analysis                           │
│                                                                 │
│  git diff <stored_commit>..HEAD --name-status                  │
│                                                                 │
│  Output:                                                        │
│    M  src/core/auth.py          (Modified)                     │
│    A  src/core/oauth.py         (Added)                        │
│    D  src/legacy/old_auth.py    (Deleted)                      │
│    R  src/utils.py -> src/helpers.py  (Renamed)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Change Classification                         │
│                                                                 │
│  1. Parse changed files                                         │
│  2. Extract affected components (classes, functions)            │
│  3. Map components to existing module tree                      │
│  4. Classify change type:                                       │
│     - All components exist in tree → Component Code Change      │
│     - New/deleted components in existing modules → Minor Rev    │
│     - Structural threshold exceeded → Major Revision            │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture

### New Components (under `codewiki/src/be/`)

```
codewiki/src/be/
├── iterative/
│   ├── __init__.py
│   ├── change_detector.py        # Git diff analysis & change classification
│   ├── module_tree_updater.py    # Module tree modifications (add/remove/recluster)
│   ├── doc_propagator.py         # Recursive documentation update propagation
│   └── iterative_generator.py    # Main orchestrator for iterative generation
```

### Component Responsibilities

#### 1. `change_detector.py`

Analyzes git changes and classifies them.

```python
class ChangeDetector:
    """Detects and classifies changes between commits."""
    
    def __init__(self, repo_path: str, config: Config):
        self.repo_path = repo_path
        self.config = config
    
    def get_changed_files(self, from_commit: str, to_commit: str = "HEAD") -> Dict[str, str]:
        """
        Get files changed between commits.
        
        Returns:
            Dict mapping file_path -> change_type ('A', 'M', 'D', 'R')
        """
        pass
    
    def extract_affected_components(
        self, 
        changed_files: Dict[str, str],
        existing_components: Dict[str, Node]
    ) -> AffectedComponents:
        """
        Parse changed files and extract affected components.
        
        Returns:
            AffectedComponents containing:
            - modified_components: List[str]  # Component IDs with code changes
            - added_components: List[str]     # New component IDs
            - deleted_components: List[str]   # Removed component IDs
        """
        pass
    
    def classify_changes(
        self,
        affected: AffectedComponents,
        module_tree: Dict[str, Any]
    ) -> ChangeClassification:
        """
        Classify the type of change required.
        
        Returns:
            ChangeClassification with:
            - change_type: 'component_change' | 'minor_revision' | 'major_revision'
            - affected_modules: List[ModulePath]  # Leaf modules affected
            - details: Dict with classification reasoning
        """
        pass
```

#### 2. `module_tree_updater.py`

Handles module tree modifications.

```python
class ModuleTreeUpdater:
    """Updates module tree structure based on changes."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def add_components_to_modules(
        self,
        module_tree: Dict[str, Any],
        new_components: List[str],
        components: Dict[str, Node]
    ) -> Dict[str, Any]:
        """
        Add new components to appropriate existing modules.
        Uses LLM to determine best module placement.
        """
        pass
    
    def remove_components_from_modules(
        self,
        module_tree: Dict[str, Any],
        deleted_components: List[str]
    ) -> Dict[str, Any]:
        """
        Remove deleted components from modules.
        Cleans up empty modules if necessary.
        """
        pass
    
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
        """
        pass
```

#### 3. `doc_propagator.py`

Handles recursive documentation updates.

```python
class DocPropagator:
    """Propagates documentation changes through the module tree."""
    
    def __init__(self, config: Config, working_dir: str):
        self.config = config
        self.working_dir = working_dir
        self._update_stack: Set[str] = set()  # Prevents infinite loops
    
    def find_affected_leaf_modules(
        self,
        module_tree: Dict[str, Any],
        affected_components: List[str]
    ) -> List[ModulePath]:
        """
        Find leaf modules containing affected components.
        """
        pass
    
    def get_modules_referencing(
        self,
        module_tree: Dict[str, Any],
        module_path: ModulePath
    ) -> List[ModulePath]:
        """
        Find modules that reference/depend on the given module.
        Uses module tree hierarchy (parent modules).
        """
        pass
    
    async def propagate_updates(
        self,
        module_tree: Dict[str, Any],
        initial_affected_modules: List[ModulePath],
        doc_changes: Dict[ModulePath, str],  # Module path -> description of changes
        components: Dict[str, Node]
    ) -> None:
        """
        Recursively propagate documentation updates.
        
        Algorithm:
        1. For each affected leaf module:
           a. Generate/update documentation with agent
           b. Record the documentation changes made
        2. Find parent modules that need updating
        3. Recursively update parents with child doc changes
        4. Use _update_stack to prevent infinite loops
        """
        pass
```

#### 4. `iterative_generator.py`

Main orchestrator for the iterative generation process.

```python
class IterativeDocumentationGenerator:
    """Orchestrates iterative documentation generation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.change_detector = ChangeDetector(config.repo_path, config)
        self.tree_updater = ModuleTreeUpdater(config)
        self.agent_orchestrator = AgentOrchestrator(config)
    
    async def run(self, force_full: bool = False) -> None:
        """
        Run iterative documentation generation.
        
        Args:
            force_full: If True, regenerate all documentation
        """
        # 1. Load existing metadata and module tree
        # 2. Get stored commit hash
        # 3. Detect and classify changes
        # 4. Route to appropriate update strategy
        # 5. Update metadata with new commit hash
        pass
    
    async def _handle_component_change(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node]
    ) -> None:
        """Handle component code changes without structural changes."""
        pass
    
    async def _handle_minor_revision(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node]
    ) -> None:
        """Handle minor revisions (add/delete components)."""
        pass
    
    async def _handle_major_revision(
        self,
        classification: ChangeClassification,
        module_tree: Dict[str, Any],
        components: Dict[str, Node],
        leaf_nodes: List[str]
    ) -> None:
        """Handle major revisions requiring re-clustering."""
        pass
```

## Process Flows

### Flow 1: Component Code Change

When existing component code is modified without adding/removing components.

```
┌──────────────────┐
│ Detect Changes   │
│ (git diff)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Extract Affected │
│ Components       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Find Affected    │
│ Leaf Modules     │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                    For Each Leaf Module                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 1. Provide agent with:                                   │ │
│  │    - Current documentation                               │ │
│  │    - Changed components (git diff)                       │ │
│  │    - Module context                                      │ │
│  │                                                          │ │
│  │ 2. Agent uses tools to update documentation:             │ │
│  │    - read_code_components (view updated code)            │ │
│  │    - str_replace_editor (modify docs)                    │ │
│  │    - generate_sub_module_documentation (if needed)       │ │
│  │                                                          │ │
│  │ 3. Record documentation changes summary                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────┬─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                  Propagate to Parent Modules                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ For each updated leaf module:                            │ │
│  │   1. Find parent module in tree                          │ │
│  │   2. Provide parent with:                                │ │
│  │      - Child documentation changes summary               │ │
│  │      - Current parent documentation                      │ │
│  │   3. LLM updates parent documentation                    │ │
│  │   4. Recursively propagate to grandparent (if exists)    │ │
│  │                                                          │ │
│  │ Loop prevention:                                         │ │
│  │   - Track updated modules in set                         │ │
│  │   - Skip if already in update stack                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Flow 2: Minor Revision

When components are added or deleted within existing modules.

```
┌──────────────────┐
│ Detect Changes   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│ Added Components │     │ Deleted Components│
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│ LLM assigns to   │     │ Remove from      │
│ existing modules │     │ module tree      │
│ (or suggests new)│     │                  │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └───────────┬────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                Update Affected Modules                        │
│                                                               │
│  1. For added components:                                     │
│     - Generate documentation section for new component        │
│     - Integrate into existing module documentation            │
│                                                               │
│  2. For deleted components:                                   │
│     - Remove references from module documentation             │
│     - Update module overview if needed                        │
│                                                               │
│  3. Propagate changes to parent modules                       │
└──────────────────────────────────────────────────────────────┘
```

### Flow 3: Major Revision

When structural changes require re-clustering (e.g., new major feature area, significant refactoring).

```
┌──────────────────┐
│ Detect Major     │
│ Changes          │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│              Determine Re-clustering Scope                    │
│                                                               │
│  Criteria for major revision:                                 │
│  - Large number of new components (threshold configurable)    │
│  - New directory/package structure detected                   │
│  - Significant portion of existing module deleted             │
│  - User explicitly requests re-clustering                     │
└────────┬─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│              Re-cluster Affected Subtree                      │
│                                                               │
│  1. Identify the subtree root that needs re-clustering        │
│  2. Gather all components under that subtree                  │
│  3. Call cluster_modules() on the subtree                     │
│  4. Merge new clustering into existing module tree            │
└────────┬─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│           Generate Documentation for New Modules              │
│                                                               │
│  1. For new leaf modules: full documentation generation       │
│  2. For modified modules: update existing documentation       │
│  3. For parent modules: regenerate based on children          │
└──────────────────────────────────────────────────────────────┘
```

## Prompt Templates

### Update Leaf Module Documentation

```python
UPDATE_LEAF_MODULE_PROMPT = """
You are updating documentation for module: {module_name}

## Context
The following changes have been made since the last documentation generation:

### Modified Components:
{modified_components_diff}

### Current Module Documentation:
{current_documentation}

### Module Tree Context:
{module_tree_context}

## Task
Update the existing documentation to reflect these changes. Focus on:
1. Updating descriptions of modified components
2. Updating any examples that may be affected
3. Updating diagrams if component relationships changed
4. Maintaining consistency with the overall documentation style

Use the available tools:
- read_code_components: To view the updated code
- str_replace_editor: To modify the documentation

Output the documentation changes you made as a brief summary at the end.
"""
```

### Propagate to Parent Module

```python
PROPAGATE_PARENT_PROMPT = """
You are updating the parent module documentation: {module_name}

## Context
The following child modules have been updated:

{child_updates_summary}

### Current Parent Documentation:
{current_parent_documentation}

## Task
Update the parent module documentation to reflect changes in child modules.
Focus on:
1. Updating the module overview if child functionality changed significantly
2. Updating cross-module interaction descriptions
3. Updating diagrams showing module relationships
4. Ensuring the parent accurately summarizes child modules

Keep changes minimal - only update what's necessary based on child changes.
"""
```

### Assign New Components to Modules

```python
ASSIGN_COMPONENTS_PROMPT = """
You are assigning new components to existing modules.

## New Components:
{new_components_list}

## Existing Module Structure:
{module_tree}

## Task
For each new component, determine which existing module it belongs to.
Consider:
1. File path proximity
2. Functional similarity
3. Import/dependency relationships

If a component doesn't fit any existing module, suggest creating a new module.

Output format:
<ASSIGNMENTS>
{
    "component_id_1": "existing_module_name",
    "component_id_2": "existing_module_name",
    "component_id_3": {"new_module": "suggested_module_name", "reason": "..."}
}
</ASSIGNMENTS>
"""
```

## Infinite Loop Prevention

The documentation propagation system includes safeguards against infinite loops:

```python
class DocPropagator:
    def __init__(self, ...):
        self._update_stack: Set[str] = set()
        self._max_propagation_depth: int = 10
        self._current_depth: int = 0
    
    async def propagate_updates(self, ...):
        module_key = "/".join(module_path)
        
        # Check for cycle
        if module_key in self._update_stack:
            logger.warning(f"Cycle detected, skipping: {module_key}")
            return
        
        # Check depth limit
        if self._current_depth >= self._max_propagation_depth:
            logger.warning(f"Max propagation depth reached: {module_key}")
            return
        
        # Add to stack before processing
        self._update_stack.add(module_key)
        self._current_depth += 1
        
        try:
            # ... perform updates ...
            
            # Propagate to parents
            parent_path = module_path[:-1]
            if parent_path:
                await self.propagate_updates(..., parent_path, ...)
        finally:
            # Remove from stack after processing
            self._update_stack.remove(module_key)
            self._current_depth -= 1
```

## CLI Integration

No new command is needed. The existing `generate` command automatically detects whether to use iterative generation by checking for existing `metadata.json`:

```bash
# Automatically uses iterative generation if metadata.json exists
codewiki generate

# Force full regeneration (ignore existing metadata)
codewiki generate --force-full

# Specify base commit (override stored commit in metadata)
codewiki generate --from-commit abc123

# Preview changes without applying
codewiki generate --dry-run
```

### Detection Logic

```python
def should_use_iterative_generation(docs_dir: str) -> bool:
    """
    Determine if iterative generation should be used.
    
    Returns True if:
    1. metadata.json exists in docs_dir
    2. metadata.json contains a valid commit_id
    3. The stored commit_id exists in git history
    4. --force-full flag is NOT set
    """
    metadata_path = os.path.join(docs_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        return False
    
    metadata = load_json(metadata_path)
    commit_id = metadata.get("generation_info", {}).get("commit_id")
    
    if not commit_id:
        return False
    
    # Verify commit exists in git history
    if not is_commit_valid(commit_id):
        logger.warning(f"Stored commit {commit_id} not found in git history")
        return False
    
    return True
```

## Metadata Schema Update

Updated `metadata.json` structure:

```json
{
  "generation_info": {
    "timestamp": "2025-01-19T10:00:00",
    "commit_id": "abc123def456...",
    "generation_type": "full|iterative",
    "main_model": "claude-sonnet-4",
    "generator_version": "1.1.0",
    "repo_path": "/path/to/repo"
  },
  "iterative_history": [
    {
      "timestamp": "2025-01-20T14:30:00",
      "from_commit": "abc123def456...",
      "to_commit": "def789ghi012...",
      "change_type": "component_change|minor_revision|major_revision",
      "affected_modules": ["module_a", "module_b"],
      "summary": "Updated authentication logic in core module"
    }
  ],
  "statistics": {
    "total_components": 150,
    "leaf_nodes": 45,
    "max_depth": 3
  },
  "files_generated": [...]
}
```

## Configuration Options

New configuration options in `Config`:

```python
@dataclass
class Config:
    # ... existing fields ...
    
    # Iterative generation settings
    iterative_enabled: bool = True
    major_revision_threshold: float = 0.3  # 30% change triggers major revision
    max_propagation_depth: int = 10
    preserve_manual_edits: bool = True  # Detect and preserve manual doc edits
```

## Edge Cases and Error Handling

### 1. No Previous Generation
If `metadata.json` doesn't exist or has no `commit_id`, fall back to full generation.

### 2. Commit Not Found
If the stored commit is no longer in git history (force push, rebase):
- Warn the user
- Offer to regenerate from scratch or from a specified commit

### 3. Merge Conflicts in Documentation
If manual edits conflict with generated updates:
- Detect manual edits by comparing stored hash of generated content
- Present conflict to user or preserve manual edits (configurable)

### 4. Module Tree Structural Mismatch
If module tree structure doesn't match current codebase:
- Detect orphaned modules (no components)
- Detect missing modules (components not in any module)
- Offer repair or full regeneration

### 5. Partial Failure Recovery
If iterative generation fails midway:
- Store progress in `.codewiki_progress.json`
- Allow resumption from last successful module

## Future Enhancements

1. **Smart Caching**: Cache LLM responses for unchanged components
2. **Parallel Updates**: Update independent modules concurrently
3. **Watch Mode**: Automatically regenerate on file save
4. **Diff Preview**: Show documentation diff before applying
5. **Rollback**: Ability to rollback to previous documentation version
6. **Cross-Repository**: Track documentation dependencies across repos

## Summary

The iterative documentation generation feature enables efficient documentation updates by:

1. **Tracking Changes**: Using git commit hashes to identify what changed
2. **Smart Classification**: Categorizing changes into component, minor, or major revisions
3. **Targeted Updates**: Only regenerating affected documentation
4. **Propagation**: Recursively updating parent modules when children change
5. **Safety**: Preventing infinite loops and handling edge cases gracefully

This approach significantly reduces documentation generation time and cost for repositories with frequent incremental changes.

