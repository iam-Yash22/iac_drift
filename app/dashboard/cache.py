from typing import Any, Dict, Optional

_CACHE: Dict[str, Any] = {}


async def get(key: str) -> Optional[Any]:
    return _CACHE.get(key)


def set(key: str, value: Any, ttl: Optional[int] = None) -> Any:
    _CACHE[key] = value
    return value


async def read(key: str) -> Optional[Any]:
    return _CACHE.get(key)


def write(key: str, value: Any, ttl: Optional[int] = None) -> Any:
    _CACHE[key] = value
    return value


def clear() -> None:
    _CACHE.clear()


__all__ = ["get", "set", "read", "write", "clear"]
