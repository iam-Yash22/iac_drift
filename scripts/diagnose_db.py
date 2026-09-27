import os
from sqlalchemy import create_engine, text
from app.db.base import Base

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    print("DB:", conn.execute(text("SELECT current_database()")).fetchone())
    tables = sorted(r[1] for r in conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")).fetchall())
    print("TABLES:", tables)
    av = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='alembic_version')")).fetchone()[0]
    print("ALEMBIC_VERSION_EXISTS:", av)
    if av:
        print("ALEMBIC_VERSION_ROWS:", conn.execute(text("SELECT version_num FROM alembic_version")).fetchall())
    if "users" in tables:
        print("USERS_COLUMNS:", sorted(c[0] for c in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'")).fetchall()))
    model_tables = set(Base.metadata.tables.keys())
    print("MODEL_TABLES_MISSING_LIVE:", model_tables - set(tables))
    print("LIVE_TABLES_NOT_IN_MODEL:", set(tables) - model_tables)
    print("DONE")
