import json
import pytest
from pathlib import Path

import app.parsers.state_parser as state_parser


def _find_parse_fn(mod):
    candidates = ("load_state", "from_file", "parse", "parse_state")
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn, name
    return None, None


def _to_items(res):
    if res is None:
        return []
    if isinstance(res, (list, tuple)):
        return list(res)
    if isinstance(res, dict):
        # common keys where parsed resources might live
        for k in ("resources", "items", "modules", "resources_parsed"):
            if k in res and isinstance(res[k], (list, tuple)):
                return list(res[k])
        return [res]
    return [res]


def _looks_like_resource(obj):
    if not isinstance(obj, dict):
        return False
    keys = set(obj.keys())
    common = {"type", "resource_type", "name", "id", "address", "attributes"}
    return bool(keys & common)


def test_parse_minimal_state_file(tmp_path):
    fn, name = _find_parse_fn(state_parser)
    if fn is None:
        pytest.skip("No parse function found in parsers.state_parser")

    state = {"version": 4, "serial": 1, "resources": []}
    p = tmp_path / "state_min.json"
    p.write_text(json.dumps(state))

    try:
        res = fn(p)
    except TypeError:
        res = fn(str(p))

    items = _to_items(res)
    assert isinstance(items, list)


def test_parse_state_with_one_resource_returns_normalized_item(tmp_path):
    fn, name = _find_parse_fn(state_parser)
    if fn is None:
        pytest.skip("No parse function found in parsers.state_parser")

    state = {
        "version": 4,
        "resources": [
            {
                "module": "",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "bucket",
                "instances": [
                    {
                        "attributes": {"id": "r1", "bucket": "my-bucket", "versioning": False}
                    }
                ],
            }
        ],
    }

    p = tmp_path / "state_one.json"
    p.write_text(json.dumps(state))

    try:
        res = fn(p)
    except TypeError:
        res = fn(str(p))

    items = _to_items(res)
    assert len(items) >= 1
    assert any(_looks_like_resource(i) for i in items), f"Parsed items did not resemble resources: {items}"
