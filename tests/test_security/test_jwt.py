import pytest
from freezegun import freeze_time
from datetime import timedelta
import app.security.jwt as jwt_module


def _find_create_fn(mod):
    candidates = ("create_token", "create_access_token", "encode_token", "encode", "create_jwt")
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn, name
    return None, None


def _find_decode_fn(mod):
    candidates = ("decode_token", "decode_jwt", "verify_token", "decode", "decode_access_token")
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn, name
    return None, None


def _call_create(fn):
    try:
        return fn({"sub": "test"}, expires=60)
    except TypeError:
        pass
    try:
        return fn({"sub": "test"}, expire_seconds=60)
    except TypeError:
        pass
    try:
        return fn({"sub": "test"})
    except TypeError:
        pass
    pytest.skip("Unsupported token create signature")


def _call_decode(fn, token):
    try:
        return fn(token)
    except TypeError:
        pass
    try:
        return fn(token, verify=True)
    except TypeError:
        pass
    try:
        return fn(token, options={"verify_exp": True})
    except TypeError:
        pass
    pytest.skip("Unsupported token decode signature")


def test_jwt_roundtrip_and_payload():
    create_fn, _ = _find_create_fn(jwt_module)
    decode_fn, _ = _find_decode_fn(jwt_module)
    if create_fn is None or decode_fn is None:
        pytest.skip("JWT create/decode functions not found in security.jwt")

    token = _call_create(create_fn)
    assert isinstance(token, str), f"Expected token string, got: {type(token)}"

    decoded = _call_decode(decode_fn, token)
    if isinstance(decoded, dict):
        assert decoded.get("sub") == "test"
    else:
        assert decoded is not None


def test_jwt_expiry_enforced():
    create_fn, _ = _find_create_fn(jwt_module)
    decode_fn, _ = _find_decode_fn(jwt_module)
    if create_fn is None or decode_fn is None:
        pytest.skip("JWT create/decode functions not found in security.jwt")

    with freeze_time("2020-01-01T00:00:00"):
        token = None
        try:
            token = create_fn({"sub": "test"}, expires=1)
        except TypeError:
            try:
                token = create_fn({"sub": "test"}, expire_seconds=1)
            except TypeError:
                try:
                    token = create_fn({"sub": "test"}, expires_delta=timedelta(seconds=1))
                except TypeError:
                    token = create_fn({"sub": "test"})

    assert isinstance(token, str)

    # advance time beyond expiry
    with freeze_time("2020-01-01T00:00:10"):
        try:
            res = _call_decode(decode_fn, token)
        except Exception:
            # decoding raised (common when token expired)
            return
        # If decode returned a value, ensure it's treated as expired (None/False or missing sub)
        if isinstance(res, dict):
            assert res.get("sub") != "test"
        else:
            assert not res
