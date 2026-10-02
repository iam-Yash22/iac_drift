import os
print("=== raw env ===")
print("CORS_ORIGINS:", repr(os.environ.get("CORS_ORIGINS")))
print("CORS__ALLOW_ORIGINS:", repr(os.environ.get("CORS__ALLOW_ORIGINS")))

from app.core.config import Settings, CORSSettings

print("=== CORSSettings() standalone ===")
print(CORSSettings().allow_origins)

print("=== Settings() direct, bypassing get_settings() ===")
print(Settings().cors.allow_origins)

from app.core.config import settings as cached_settings
print("=== module-level cached `settings` ===")
print(cached_settings.cors.allow_origins)
