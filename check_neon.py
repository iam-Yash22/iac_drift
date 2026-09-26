from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'])
conn = engine.connect()
result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1"))
print('tables:', result.fetchall())
