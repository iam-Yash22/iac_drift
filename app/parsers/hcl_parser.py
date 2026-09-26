"""Utilities for parsing Terraform HCL source files and attaching source metadata.

This module intentionally keeps the dependency surface small: the underlying
Terraform parser is exposed via hcl2, and the common app constants are imported
through the shared core package.
"""

import hcl2
from pathlib import Path
from app.core.constants import DriftType

__all__ = [
    "parse_hcl",
    "parse_hcl_text",
    "parse_hcl_file",
    "parse_tf_file",
    "load_tf_file",
    "extract_resource_locations",
    "find_resource_locations",
    "extract_resources",
    "iter_resources",
    "resource_map",
    "_classify_drift",
]


def parse_hcl_text(source):
    """Parse raw HCL text into a Python dictionary."""
    if source is None:
        return {}
    if hasattr(source, "read"):
        source = source.read()
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    if not isinstance(source, str):
        source = str(source)
    try:
        return hcl2.loads(source)
    except Exception as exc:
        raise ValueError(f"Invalid HCL content: {exc}") from exc


def parse_hcl(source):
    """Parse either raw HCL text or an HCL file path."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists():
            return parse_hcl_file(path)
    return parse_hcl_text(source)


def parse_hcl_file(path):
    """Read a Terraform source file and parse the HCL payload."""
    file_path = Path(path)
    return parse_hcl_text(file_path.read_text(encoding="utf-8"))


def parse_tf_file(path):
    """Compatibility wrapper for Terraform file parsing."""
    return parse_hcl_file(path)


def load_tf_file(path):
    """Alias used by callers that expect a load helper."""
    return parse_hcl_file(path)


def _line_number_at(text, index):
    return text.count("\n", 0, index) + 1


def _find_block_end(text, start_index):
    """Return the closing brace position for the block starting at start_index."""
    depth = 0
    in_string = False
    quote = None
    escape = False
    index = start_index
    while index < len(text):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        index += 1
    return len(text) - 1


def extract_resource_locations(source, source_file=None):
    """Extract resource block positions with file and line metadata."""
    if source is None:
        return []
    if hasattr(source, "read"):
        source = source.read()
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    if isinstance(source, Path):
        source_file = str(source)
        source = source.read_text(encoding="utf-8")
    if not isinstance(source, str):
        source = str(source)

    results = []
    cursor = 0
    while cursor < len(source):
        token_index = source.find("resource", cursor)
        if token_index < 0:
            break
        if token_index > 0 and source[token_index - 1] not in " \t\n\r":
            cursor = token_index + 1
            continue
        next_index = token_index + len("resource")
        if next_index < len(source) and source[next_index] not in " \t\n\r":
            cursor = next_index
            continue

        index = next_index
        while index < len(source) and source[index].isspace():
            index += 1
        if index >= len(source) or source[index] != '"':
            cursor = token_index + 1
            continue

        start_type = index + 1
        index += 1
        while index < len(source) and source[index] != '"':
            if source[index] == "\\":
                index += 2
                continue
            index += 1
        if index >= len(source):
            break
        resource_type = source[start_type:index]
        index += 1
        while index < len(source) and source[index].isspace():
            index += 1
        if index >= len(source) or source[index] != '"':
            cursor = token_index + 1
            continue

        start_name = index + 1
        index += 1
        while index < len(source) and source[index] != '"':
            if source[index] == "\\":
                index += 2
                continue
            index += 1
        if index >= len(source):
            break
        resource_name = source[start_name:index]
        index += 1
        while index < len(source) and source[index].isspace():
            index += 1
        if index >= len(source) or source[index] != '{':
            cursor = token_index + 1
            continue

        block_start = index
        block_end = _find_block_end(source, block_start)
        if block_end <= block_start:
            block_end = len(source) - 1

        start_line = _line_number_at(source, token_index)
        end_line = _line_number_at(source, block_end)
        results.append(
            {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "resource_id": f"{resource_type}.{resource_name}",
                "line": start_line,
                "line_number": start_line,
                "start_line": start_line,
                "end_line": end_line,
                "source_file": str(source_file) if source_file else None,
                "source_path": str(source_file) if source_file else None,
                "file": str(source_file) if source_file else None,
            }
        )
        cursor = block_end + 1
    return results


def find_resource_locations(source, resource_type=None, resource_name=None, source_file=None):
    """Filter discovered resource locations by type/name when provided."""
    matches = extract_resource_locations(source, source_file=source_file)
    filtered = []
    for match in matches:
        if resource_type and match["resource_type"] != resource_type:
            continue
        if resource_name and match["resource_name"] != resource_name:
            continue
        filtered.append(match)
    return filtered


def _normalize_resource_entry(resource_type, resource_name, body, source_file=None, line=None, end_line=None):
    record = {
        "resource_type": resource_type,
        "resource_name": resource_name,
        "resource_id": f"{resource_type}.{resource_name}",
        "data": body,
        "source_file": str(source_file) if source_file else None,
        "source_path": str(source_file) if source_file else None,
        "file": str(source_file) if source_file else None,
        "line": int(line) if line is not None else None,
        "line_number": int(line) if line is not None else None,
        "start_line": int(line) if line is not None else None,
        "end_line": int(end_line) if end_line is not None else None,
    }
    record["source"] = {
        "file": record["source_file"],
        "line": record["line"],
        "start_line": record["start_line"],
        "end_line": record["end_line"],
    }
    return record


def _strip_hcl_key(value):
    if isinstance(value, str):
        return value.strip('"')
    return value


def _collect_resources(node, source_file=None, resource_locations=None):
    results = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "resource":
                if isinstance(value, list):
                    for block in value:
                        if not isinstance(block, dict):
                            continue
                        for resource_type, blocks in block.items():
                            resource_type = _strip_hcl_key(resource_type)
                            if resource_type == "__is_block__":
                                continue
                            if isinstance(blocks, dict):
                                for resource_name, body in blocks.items():
                                    if resource_name == "__is_block__":
                                        continue
                                    resource_name = _strip_hcl_key(resource_name)
                                    line_meta = None
                                    end_line = None
                                    if resource_locations:
                                        for item in resource_locations:
                                            if item["resource_type"] == resource_type and item["resource_name"] == resource_name:
                                                line_meta = item["line"]
                                                end_line = item["end_line"]
                                                break
                                    results.append(_normalize_resource_entry(resource_type, resource_name, body, source_file, line_meta, end_line))
                            elif isinstance(blocks, list):
                                for item in blocks:
                                    if not isinstance(item, dict):
                                        continue
                                    for resource_name, body in item.items():
                                        if resource_name == "__is_block__":
                                            continue
                                        resource_name = _strip_hcl_key(resource_name)
                                        line_meta = None
                                        end_line = None
                                        if resource_locations:
                                            for meta in resource_locations:
                                                if meta["resource_type"] == resource_type and meta["resource_name"] == resource_name:
                                                    line_meta = meta["line"]
                                                    end_line = meta["end_line"]
                                                    break
                                        results.append(_normalize_resource_entry(resource_type, resource_name, body, source_file, line_meta, end_line))
                elif isinstance(value, dict):
                    for resource_type, blocks in value.items():
                        resource_type = _strip_hcl_key(resource_type)
                        if resource_type == "__is_block__":
                            continue
                        if isinstance(blocks, dict):
                            for resource_name, body in blocks.items():
                                if resource_name == "__is_block__":
                                    continue
                                resource_name = _strip_hcl_key(resource_name)
                                line_meta = None
                                end_line = None
                                if resource_locations:
                                    for item in resource_locations:
                                        if item["resource_type"] == resource_type and item["resource_name"] == resource_name:
                                            line_meta = item["line"]
                                            end_line = item["end_line"]
                                            break
                                results.append(_normalize_resource_entry(resource_type, resource_name, body, source_file, line_meta, end_line))
            else:
                results.extend(_collect_resources(value, source_file=source_file, resource_locations=resource_locations))
    elif isinstance(node, list):
        for item in node:
            results.extend(_collect_resources(item, source_file=source_file, resource_locations=resource_locations))
    return results


def extract_resources(document, source_file=None):
    """Extract Terraform resource blocks and attach source metadata when available."""
    if isinstance(document, (str, Path)):
        source_file = str(document) if isinstance(document, Path) else source_file
        document = parse_hcl(document)

    resource_locations = []
    if isinstance(document, str):
        resource_locations = extract_resource_locations(document, source_file=source_file)
        document = parse_hcl_text(document)

    if source_file:
        try:
            raw_text = Path(source_file).read_text(encoding="utf-8")
            resource_locations = extract_resource_locations(raw_text, source_file=source_file)
        except Exception:
            pass

    return _collect_resources(document, source_file=source_file, resource_locations=resource_locations)


def iter_resources(document, source_file=None):
    """Iterate over parsed Terraform resource entries."""
    for item in extract_resources(document, source_file=source_file):
        yield item


def resource_map(document, source_file=None):
    """Map resource identifiers to metadata dictionaries."""
    mapping = {}
    for record in extract_resources(document, source_file=source_file):
        mapping[record["resource_id"]] = record
    return mapping


def _classify_drift(record):
    """Resolve a convenient drift label for code-only resources."""
    if record is None:
        return DriftType.UNMANAGED
    return DriftType.UNMANAGED
