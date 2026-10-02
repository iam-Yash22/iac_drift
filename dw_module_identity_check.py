import app.middleware as m
import inspect
import sys

print("=== module file ===")
print(m.__file__)

print("=== actual source of _resolve_cors_origins ===")
print(inspect.getsource(m._resolve_cors_origins))

print("=== sys.path (first 5) ===")
for p in sys.path[:5]:
    print(p)

print("=== direct call ===")
print(m._resolve_cors_origins())
