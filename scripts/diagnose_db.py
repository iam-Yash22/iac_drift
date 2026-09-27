import sys
sys.path.insert(0, "/app")
import os
from sqlalchemy import create_engine, text
from app.core.config import settings

raw_url = os.environ.get("DATABASE_URL")
raw_nested = os.environ.get("DATABASE__URL")
resolved = str(settings.database.url) if settings.database.url else None

print("RAW_DATABASE_URL_HOST:", raw_url.split("@")[-1] if raw_url else None)
print("RAW_DATABASE__URL_HOST:", raw_nested.split("@")[-1] if raw_nested else None)
print("RESOLVED_SETTINGS_URL_HOST:", resolved.split("@")[-1] if resolved else None)
print("RAW_MATCHES_RESOLVED:", raw_url == resolved)

engine = create_engine(resolved)
with engine.connect() as conn:
    print("RESOLVED_DB_TABLES:", sorted(r[1] for r in conn.execute(text(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')"
    )).fetchall()))
print("DONE")
