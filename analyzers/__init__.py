"""Plugin-based analyzer registry.

Analyzers are auto-discovered from this package at import time.
Each analyzer module registers itself using the @register decorator.

Usage:
    from analyzers import get_analyzer, get_all_analysis_types

    analyzer = get_analyzer("short_dumps")
    if analyzer:
        result = analyzer.analyze(rows, context)

To add a new analyzer:
    1. Create analyzers/<domain>.py
    2. Define a function decorated with @register("analysis_type_name")
    3. That's it — no other files need changing.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

# Type for analyzer functions: (rows: list[dict], context: str) -> dict
AnalyzerFn = Callable[[list[dict], str], dict[str, Any]]

# Registry: analysis_type → analyzer function
_REGISTRY: dict[str, AnalyzerFn] = {}

# Reverse map: analysis_type → module name (for debugging)
_REGISTRY_SOURCE: dict[str, str] = {}


def register(*analysis_types: str):
    """Decorator to register an analyzer function for one or more analysis_types.

    Usage:
        @register("short_dumps")
        def analyze_short_dumps(rows: list[dict], context: str) -> dict:
            ...

        @register("availability", "SAP_system_availability", "SAP_Process_Availability")
        def analyze_availability(rows: list[dict], context: str) -> dict:
            ...
    """
    def decorator(fn: AnalyzerFn) -> AnalyzerFn:
        for atype in analysis_types:
            _REGISTRY[atype] = fn
            _REGISTRY_SOURCE[atype] = fn.__module__
        return fn
    return decorator


def get_analyzer(analysis_type: str) -> AnalyzerFn | None:
    """Look up an analyzer by analysis_type. Returns None if not registered."""
    return _REGISTRY.get(analysis_type)


def get_all_analysis_types() -> frozenset[str]:
    """Return all registered analysis types (replaces CLASSIFIED_ANALYSIS_TYPES)."""
    return frozenset(_REGISTRY.keys())


def list_analyzers() -> list[dict]:
    """List all registered analyzers with their source modules (for debugging)."""
    return [
        {"analysis_type": k, "module": v}
        for k, v in sorted(_REGISTRY_SOURCE.items())
    ]


# ── Auto-discovery: import all modules in this package ─────────────────────────
def _discover_analyzers() -> None:
    """Import all modules in the analyzers package to trigger @register decorators."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f".{module_info.name}", package=__name__)


_discover_analyzers()
