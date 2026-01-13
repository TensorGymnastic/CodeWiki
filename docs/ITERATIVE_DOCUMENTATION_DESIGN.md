# Iterative Documentation Generation - Design Document

> **Status**: Proposal  
> **Created**: 2026-01-12  
> **Author**: CodeWiki Team

## Overview

This document outlines the design for **iterative/incremental documentation generation** in CodeWiki. Instead of regenerating all documentation from scratch on each run, this feature allows CodeWiki to detect code changes since the last generation and update only the affected modules.

## Motivation

- **Efficiency**: Large codebases take significant time and API tokens to document fully
- **Cost Reduction**: Only regenerate what changed, reducing LLM API costs
- **Faster Feedback**: Developers can quickly update docs after small changes
- **Preserve Manual Edits**: Potential to preserve user modifications to generated docs

## Current State

The existing codebase already has foundations for this feature:

| Component | Location | Current Capability |
|-----------|----------|-------------------|
| `metadata.json` | Output directory | Stores `commit_id` in `generation_info` |
| `GitManager` | `cli/git_manager.py` | Has `get_commit_hash()` method |
| `module_tree.json` | Output directory | Tracks components per module |
| Dependency graph | `dependency_analyzer/` | Shows relationships between components |

---

## Proposed Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Load metadata.json → get stored commit_hash              │
│ 2. git diff --name-only <stored_hash>..HEAD                 │
│ 3. Map changed files → affected leaf nodes                  │
│ 4. Traverse module tree upward → find affected modules      │
│ 5. Regenerate affected modules (leaf-first, then parents)   │
│ 6. Update metadata.json with new commit_hash                │
└─────────────────────────────────────────────────────────────┘
```

### Tiered Regeneration Strategy

Changes are classified into three tiers based on their scope and impact:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Change Analysis Phase                         │
├─────────────────────────────────────────────────────────────────┤
│  TIER 1: Content-only changes                                   │
│    - Modified files that stay in same modules                   │
│    → Regenerate affected modules only                           │
│                                                                 │
│  TIER 2: Module membership changes                              │
│    - New files need assignment                                  │
│    - Deleted files leave modules                                │
│    → Incremental module adjustment + regeneration               │
│                                                                 │
│  TIER 3: Structural changes                                     │
│    - New directories/packages                                   │
│    - Significant deletions                                      │
│    - Rename/move operations                                     │
│    → Partial or full re-clustering                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Design

### 1. Change Detection

#### 1.1 Git-Based Change Detection

Extend `GitManager` with new methods:

```python
# cli/git_manager.py

def get_changed_files_since(self, commit_hash: str) -> Dict[str, List[str]]:
    """
    Get files changed since a specific commit.
    
    Args:
        commit_hash: The base commit to compare against
        
    Returns:
        Dictionary with keys: "added", "modified", "deleted", "renamed"
    """
    diff = self.repo.git.diff('--name-status', f'{commit_hash}..HEAD')
    
    changes = {"added": [], "modified": [], "deleted": [], "renamed": []}
    for line in diff.strip().split('\n'):
        if not line:
            continue
        status, *paths = line.split('\t')
        if status == 'A':
            changes["added"].append(paths[0])
        elif status == 'M':
            changes["modified"].append(paths[0])
        elif status == 'D':
            changes["deleted"].append(paths[0])
        elif status.startswith('R'):
            changes["renamed"].append({"from": paths[0], "to": paths[1]})
    
    return changes
```

#### 1.2 Change Scope Analysis

```python
# cli/change_detector.py (NEW FILE)

from enum import Enum
from typing import Dict, Set, List
from pathlib import Path

class ChangeScope(Enum):
    INCREMENTAL = "incremental"           # < 10% changes
    PARTIAL_RECLUSTER = "partial_recluster"  # 10-40% changes
    FULL_RESTRUCTURE = "full_restructure"    # > 40% changes

class ChangeDetector:
    def __init__(self, 
                 repo_path: Path, 
                 metadata: Dict,
                 major_threshold: float = 0.3,
                 restructure_threshold: float = 0.5):
        self.repo_path = repo_path
        self.metadata = metadata
        self.major_threshold = major_threshold
        self.restructure_threshold = restructure_threshold
    
    def get_base_commit(self) -> Optional[str]:
        """Get the commit hash from last documentation generation."""
        return self.metadata.get("generation_info", {}).get("commit_id")
    
    def analyze_change_scope(self, changes: Dict[str, List]) -> ChangeScope:
        """Determine the scope of changes to decide regeneration strategy."""
        total_files = self._count_source_files()
        changed_count = (
            len(changes["added"]) + 
            len(changes["modified"]) + 
            len(changes["deleted"])
        )
        
        if total_files == 0:
            return ChangeScope.FULL_RESTRUCTURE
            
        change_ratio = changed_count / total_files
        
        if change_ratio >= self.restructure_threshold:
            return ChangeScope.FULL_RESTRUCTURE
        elif change_ratio >= self.major_threshold or len(changes["added"]) > 10:
            return ChangeScope.PARTIAL_RECLUSTER
        else:
            return ChangeScope.INCREMENTAL
    
    def get_affected_components(self, 
                                 changes: Dict[str, List],
                                 components: Dict) -> Set[str]:
        """Map changed files to affected component IDs."""
        affected = set()
        changed_files = set(changes["added"] + changes["modified"])
        
        for comp_id, comp_info in components.items():
            if comp_info.file_path in changed_files:
                affected.add(comp_id)
        
        return affected
    
    def get_affected_modules(self,
                              affected_components: Set[str],
                              module_tree: Dict) -> List[str]:
        """
        Find all modules affected by component changes.
        Includes parent modules (changes bubble up).
        """
        affected_modules = set()
        
        def find_modules(tree: Dict, path: List[str] = []):
            for module_name, module_info in tree.items():
                current_path = path + [module_name]
                module_key = "/".join(current_path)
                
                # Check if any component in this module is affected
                module_components = set(module_info.get("components", []))
                if module_components & affected_components:
                    # Add this module and all parent modules
                    for i in range(len(current_path)):
                        affected_modules.add("/".join(current_path[:i+1]))
                
                # Recurse into children
                if "children" in module_info:
                    find_modules(module_info["children"], current_path)
        
        find_modules(module_tree)
        return list(affected_modules)
```

### 2. Structural Change Handling

#### 2.1 New Files - Module Assignment

For new files that need to be assigned to modules:

```python
# cli/incremental_clusterer.py (NEW FILE)

INCREMENTAL_CLUSTER_PROMPT = """
You are assigning new code components to an existing module structure.

## Existing Module Structure:
{existing_module_tree}

## New Components to Assign:
{new_components}

For each new component, decide:
1. **assign** - Add to an existing module
2. **new_module** - Create a new top-level module
3. **new_submodule** - Create a new submodule under an existing module

Consider:
- File paths and naming conventions
- Functional similarity to existing modules
- Dependency relationships

## Output Format (JSON):
{{
  "assignments": [
    {{"component": "ComponentName", "action": "assign", "module_path": ["Parent", "Child"]}},
    {{"component": "NewService", "action": "new_module", "name": "ModuleName", "description": "..."}},
    {{"component": "Helper", "action": "new_submodule", "parent": ["Existing"], "name": "SubName"}}
  ]
}}
"""

class IncrementalClusterer:
    def __init__(self, config: Config):
        self.config = config
    
    def assign_new_components(self,
                               new_components: List[Dict],
                               existing_module_tree: Dict) -> Dict:
        """Use LLM to assign new components to modules."""
        prompt = INCREMENTAL_CLUSTER_PROMPT.format(
            existing_module_tree=json.dumps(existing_module_tree, indent=2),
            new_components=json.dumps(new_components, indent=2)
        )
        
        response = call_llm(prompt, self.config)
        assignments = json.loads(response)
        
        return self._apply_assignments(existing_module_tree, assignments)
    
    def _apply_assignments(self, 
                           module_tree: Dict, 
                           assignments: Dict) -> Dict:
        """Apply component assignments to module tree."""
        updated_tree = deepcopy(module_tree)
        
        for assignment in assignments["assignments"]:
            if assignment["action"] == "assign":
                self._add_to_module(
                    updated_tree, 
                    assignment["module_path"],
                    assignment["component"]
                )
            elif assignment["action"] == "new_module":
                updated_tree[assignment["name"]] = {
                    "description": assignment.get("description", ""),
                    "components": [assignment["component"]],
                    "children": {}
                }
            elif assignment["action"] == "new_submodule":
                self._add_submodule(
                    updated_tree,
                    assignment["parent"],
                    assignment["name"],
                    assignment["component"]
                )
        
        return updated_tree
```

#### 2.2 Deleted Files - Module Pruning

```python
# cli/module_pruner.py (NEW FILE)

class ModulePruner:
    def __init__(self, min_components: int = 1):
        self.min_components = min_components
    
    def remove_components(self,
                          module_tree: Dict,
                          deleted_components: Set[str]) -> Dict:
        """Remove deleted components from module tree."""
        
        def prune_recursive(node: Dict) -> Dict:
            result = {}
            for module_name, module_info in node.items():
                new_info = deepcopy(module_info)
                
                # Remove deleted components
                if "components" in new_info:
                    new_info["components"] = [
                        c for c in new_info["components"]
                        if c not in deleted_components
                    ]
                
                # Recursively prune children
                if "children" in new_info and new_info["children"]:
                    new_info["children"] = prune_recursive(new_info["children"])
                
                # Keep module if it has components or non-empty children
                if new_info.get("components") or new_info.get("children"):
                    result[module_name] = new_info
            
            return result
        
        return prune_recursive(module_tree)
    
    def merge_sparse_modules(self, 
                              module_tree: Dict,
                              parent_path: List[str] = []) -> Dict:
        """Merge modules that have too few components with their siblings or parent."""
        # Implementation for merging sparse modules after deletions
        pass
```

#### 2.3 New Directory Detection

```python
# cli/structure_analyzer.py (NEW FILE)

@dataclass
class StructuralChanges:
    new_directories: Set[str]
    deleted_directories: Set[str]
    potential_new_modules: List[Dict]
    orphaned_modules: List[str]

class StructureAnalyzer:
    def __init__(self, module_threshold: int = 3):
        self.module_threshold = module_threshold
    
    def detect_structural_changes(self,
                                   old_files: Set[str],
                                   new_files: Set[str],
                                   changes: Dict) -> StructuralChanges:
        """Detect if directory structure changed significantly."""
        
        old_dirs = {str(Path(p).parent) for p in old_files}
        current_dirs = {str(Path(p).parent) for p in new_files}
        
        new_directories = current_dirs - old_dirs
        deleted_directories = old_dirs - current_dirs
        
        # Identify potential new modules
        potential_new_modules = []
        for new_dir in new_directories:
            files_in_dir = [
                f for f in changes["added"] 
                if str(Path(f).parent) == new_dir
            ]
            if len(files_in_dir) >= self.module_threshold:
                potential_new_modules.append({
                    "path": new_dir,
                    "files": files_in_dir,
                    "suggested_name": Path(new_dir).name.title()
                })
        
        return StructuralChanges(
            new_directories=new_directories,
            deleted_directories=deleted_directories,
            potential_new_modules=potential_new_modules,
            orphaned_modules=[]  # Computed separately
        )
```

### 3. Selective Regeneration

```python
# cli/selective_regenerator.py (NEW FILE)

class SelectiveRegenerator:
    def __init__(self, 
                 repo_path: Path,
                 output_dir: Path,
                 config: Dict):
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.config = config
    
    async def regenerate_modules(self,
                                  affected_modules: List[str],
                                  module_tree: Dict,
                                  components: Dict) -> Dict:
        """
        Regenerate only the affected modules.
        
        Processes in correct order:
        1. Leaf modules first (parallel where possible)
        2. Parent modules after their children complete
        """
        # Sort modules by depth (deepest first)
        sorted_modules = self._sort_by_depth(affected_modules)
        
        for module_path in sorted_modules:
            module_info = self._get_module_info(module_tree, module_path)
            
            if self._is_leaf_module(module_info):
                # Regenerate leaf module documentation
                await self._regenerate_leaf_module(
                    module_path, module_info, components
                )
            else:
                # Re-roll-up parent module from children docs
                await self._regenerate_parent_module(
                    module_path, module_info
                )
        
        return module_tree
    
    def _sort_by_depth(self, modules: List[str]) -> List[str]:
        """Sort modules by depth (deepest first for bottom-up processing)."""
        return sorted(modules, key=lambda m: -m.count('/'))
```

### 4. Enhanced Metadata Schema

```json
{
  "generation_info": {
    "timestamp": "2026-01-12T10:30:00Z",
    "commit_id": "def456789...",
    "base_commit_id": "abc123456...",
    "strategy_used": "partial_recluster",
    "generator_version": "1.1.0",
    "repo_path": "/path/to/repo"
  },
  "statistics": {
    "total_components": 150,
    "leaf_nodes": 45,
    "modules_generated": 12,
    "modules_regenerated": 3,
    "tokens_used": 50000
  },
  "module_tracking": {
    "Authentication": {
      "components": ["LoginController", "AuthService", "TokenManager"],
      "source_files": [
        "src/auth/login.py",
        "src/auth/service.py",
        "src/auth/tokens.py"
      ],
      "created_at": "2026-01-10T08:00:00Z",
      "last_modified": "2026-01-12T10:30:00Z",
      "doc_hash": "sha256:abc123...",
      "generation_history": [
        {"commit": "abc123", "action": "created", "timestamp": "2026-01-10T08:00:00Z"},
        {"commit": "def456", "action": "regenerated", "reason": "content_change", "timestamp": "2026-01-12T10:30:00Z"}
      ]
    },
    "Payments": {
      "components": ["PaymentService", "StripeClient"],
      "source_files": ["src/payments/service.py", "src/payments/stripe.py"],
      "created_at": "2026-01-12T10:30:00Z",
      "last_modified": "2026-01-12T10:30:00Z",
      "generation_history": [
        {"commit": "def456", "action": "created", "reason": "new_directory", "timestamp": "2026-01-12T10:30:00Z"}
      ]
    }
  },
  "structural_changes_history": {
    "def456": {
      "timestamp": "2026-01-12T10:30:00Z",
      "scope": "partial_recluster",
      "new_modules": ["Payments"],
      "deleted_modules": [],
      "regenerated_modules": ["Authentication", "API"],
      "files_added": 3,
      "files_modified": 5,
      "files_deleted": 1
    }
  }
}
```

### 5. CLI Command

```python
# cli/commands/regenerate.py (NEW FILE)

@click.command(name="regenerate")
@click.option(
    "--since",
    type=str,
    default=None,
    help="Base commit hash (default: from metadata)"
)
@click.option(
    "--strategy",
    type=click.Choice(['auto', 'incremental', 'recluster', 'full']),
    default='auto',
    help="Regeneration strategy"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be regenerated without making changes"
)
@click.option(
    "--force-modules",
    type=str,
    default=None,
    help="Comma-separated list of modules to force regenerate"
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Interactive mode for structural changes"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress"
)
@click.pass_context
def regenerate_command(ctx, since, strategy, dry_run, force_modules, interactive, verbose):
    """
    Incrementally update documentation based on code changes.
    
    This command analyzes changes since the last documentation generation
    and updates only the affected modules, saving time and API costs.
    
    Examples:
    
    \b
    # Auto-detect changes and regenerate
    $ codewiki regenerate
    
    \b
    # Preview what would be regenerated
    $ codewiki regenerate --dry-run
    
    \b
    # Force specific strategy
    $ codewiki regenerate --strategy incremental
    
    \b
    # Regenerate from specific commit
    $ codewiki regenerate --since abc123
    
    \b
    # Force regenerate specific modules
    $ codewiki regenerate --force-modules "Authentication,API"
    
    \b
    # Interactive mode for new module assignment
    $ codewiki regenerate --interactive
    """
    # Implementation
    pass
```

---

## Decision Tree

```
                    Start: codewiki regenerate
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Load metadata.json  │
                    │ Get stored commit   │
                    └──────────┬──────────┘
                              │
                    ┌─────────▼─────────┐
                    │ metadata exists?  │
                    └─────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              │ NO                            │ YES
              ▼                               ▼
      Full generation               git diff --name-status
      (same as `generate`)          Categorize: A/M/D/R
                                              │
                              ┌───────────────┴───────────────┐
                              │     Compute change ratio      │
                              │  (changed + new + del) / total│
                              └───────────────┬───────────────┘
                                              │
                ┌─────────────────────────────┼─────────────────────────────┐
                │                             │                             │
                ▼                             ▼                             ▼
           ratio < 10%                10% ≤ ratio < 40%               ratio ≥ 40%
                │                             │                             │
                ▼                             ▼                             ▼
           INCREMENTAL              PARTIAL_RECLUSTER              FULL_RESTRUCTURE
                │                             │                             │
                ▼                             ▼                             ▼
        ┌───────────────┐          ┌───────────────────┐         ┌─────────────────┐
        │ Map changes   │          │ Incremental       │         │ Re-run          │
        │ to modules    │          │ cluster new files │         │ cluster_modules │
        │ Regenerate    │          │ Prune deleted     │         │ Regenerate all  │
        │ affected only │          │ Regenerate        │         │ Fresh metadata  │
        │ Update commit │          │ Update module_tree│         │                 │
        └───────────────┘          └───────────────────┘         └─────────────────┘
```

---

## Edge Cases

| Scenario | Detection | Behavior |
|----------|-----------|----------|
| **Metadata missing** | `metadata.json` not found | Fall back to full generation |
| **Base commit not found** | Git can't find stored commit | Warn user, offer full regen |
| **Deleted files orphan module** | Module has 0 components | Remove module, delete `.md` |
| **File renamed** | Git detects `R` status | Update paths, preserve module |
| **Manual doc edits** | Doc hash mismatch | Warn user, offer `--preserve` |
| **Circular dependencies** | Detection during analysis | Log warning, process anyway |
| **Large new package** | >10 files in new directory | Suggest new module creation |

---

## Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Extend `GitManager` with `get_changed_files_since()`
- [ ] Create `ChangeDetector` class
- [ ] Implement basic `regenerate` command (Tier 1 only)
- [ ] Update `metadata.json` schema with `base_commit_id`

### Phase 2: Module Membership
- [ ] Create `IncrementalClusterer` for new file assignment
- [ ] Create `ModulePruner` for handling deletions
- [ ] Implement Tier 2 regeneration logic
- [ ] Add `--interactive` mode for ambiguous assignments

### Phase 3: Full Structural Changes
- [ ] Create `StructureAnalyzer` for directory changes
- [ ] Implement Tier 3 with automatic threshold detection
- [ ] Add `--strategy` option for user override
- [ ] Implement `--dry-run` preview

### Phase 4: Polish
- [ ] Add comprehensive logging and progress reporting
- [ ] Implement `--force-modules` option
- [ ] Add generation history tracking
- [ ] Write tests for all scenarios

---

## Open Questions

1. **Re-clustering policy**: When should we re-run full clustering vs. incremental assignment?
   - Current proposal: Based on change ratio thresholds

2. **Manual edit preservation**: How to handle user modifications to generated docs?
   - Option A: Always overwrite (simple)
   - Option B: Detect via hash, warn and offer `--preserve`
   - Option C: Use git merge strategies

3. **Cross-module dependencies**: If module A references module B, and B changes, should A be regenerated?
   - Conservative: Yes, always propagate
   - Aggressive: Only if public API changed

4. **History retention**: How much generation history to keep?
   - Proposal: Last 10 runs or 30 days

---

## References

- [Current `documentation_generator.py`](../codewiki/src/be/documentation_generator.py)
- [Current `git_manager.py`](../codewiki/cli/git_manager.py)
- [Module clustering logic](../codewiki/src/be/cluster_modules.py)
