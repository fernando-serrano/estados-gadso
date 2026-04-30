"""Subflujo para Consultas > Busqueda de vigilantes."""

from .navigation import navigate_to_busqueda_vigilantes
from .search import process_records_in_busqueda_vigilantes, search_record_and_open_detail

__all__ = [
    "navigate_to_busqueda_vigilantes",
    "process_records_in_busqueda_vigilantes",
    "search_record_and_open_detail",
]
