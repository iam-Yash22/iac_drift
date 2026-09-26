"""Normalization entry point for live AWS resource payloads."""

from typing import Any

from app.parsers.normalizer import normalize_collection, normalize_resources


def normalize_live_resources(payload: Any):
    """Normalize AWS fetcher output into canonical resource records."""
    return normalize_collection(payload)


def parse_live_resources(payload: Any):
    """Compatibility alias for live resource normalization."""
    return normalize_live_resources(payload)


__all__ = ["normalize_live_resources", "parse_live_resources", "normalize_resources"]
