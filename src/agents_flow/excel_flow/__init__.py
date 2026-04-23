"""Subflujo para entrada/salida Excel."""

from .records import (
    InputRecord,
    SearchResult,
    ensure_data_dirs,
    load_input_records,
    resolve_input_excel,
    write_search_results,
)

__all__ = [
    "InputRecord",
    "SearchResult",
    "ensure_data_dirs",
    "load_input_records",
    "resolve_input_excel",
    "write_search_results",
]
