"""Compatibility entry point for Terraform state parsing."""

from app.parsers.state_parser import (
    load_state,
    normalize_resources,
    parse_resources,
    parse_state,
    parse_state_file,
)

__all__ = [
    "load_state",
    "normalize_resources",
    "parse_resources",
    "parse_state",
    "parse_state_file",
]
