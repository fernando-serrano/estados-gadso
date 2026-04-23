"""Subflujo para extraccion estructurada de datos del registro."""

from .courses import COURSE_OUTPUT_FIELDS, extract_course_fields
from .detail import DETAIL_OUTPUT_FIELDS, extract_detail_fields
from .history import HISTORY_OUTPUT_FIELDS, extract_history_fields
from .license import LICENSE_OUTPUT_FIELDS, extract_license_fields

OUTPUT_FIELDS = [
    *DETAIL_OUTPUT_FIELDS,
    *COURSE_OUTPUT_FIELDS,
    *LICENSE_OUTPUT_FIELDS,
    *HISTORY_OUTPUT_FIELDS,
]

__all__ = [
    "COURSE_OUTPUT_FIELDS",
    "DETAIL_OUTPUT_FIELDS",
    "HISTORY_OUTPUT_FIELDS",
    "LICENSE_OUTPUT_FIELDS",
    "OUTPUT_FIELDS",
    "extract_course_fields",
    "extract_detail_fields",
    "extract_history_fields",
    "extract_license_fields",
]
