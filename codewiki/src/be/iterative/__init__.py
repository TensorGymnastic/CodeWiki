"""
Iterative documentation generation module.

This module provides functionality for incrementally updating documentation
based on git changes since the last generation, rather than regenerating
everything from scratch.
"""

from codewiki.src.be.iterative.change_detector import ChangeDetector, AffectedComponents, ChangeClassification
from codewiki.src.be.iterative.module_tree_updater import ModuleTreeUpdater
from codewiki.src.be.iterative.doc_propagator import DocPropagator
from codewiki.src.be.iterative.iterative_generator import IterativeDocumentationGenerator

__all__ = [
    'ChangeDetector',
    'AffectedComponents', 
    'ChangeClassification',
    'ModuleTreeUpdater',
    'DocPropagator',
    'IterativeDocumentationGenerator',
]
