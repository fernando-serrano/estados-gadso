"""Subflujo para Consultas > Mis vigilantes."""

from .navigation import navigate_to_mis_vigilantes
from .search import process_records_in_mis_vigilantes, search_record_and_open_detail

__all__ = [
    "navigate_to_mis_vigilantes",
    "process_records_in_mis_vigilantes",
    "search_record_and_open_detail",
]
