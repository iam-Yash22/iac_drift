"""Quick database connectivity and schema check."""
from sqlalchemy import create_engine, inspect
from app.core.config import settings

try:
    engine = create_engine(str(settings.database.url))
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f'✓ Connected successfully to database!')
    print(f'\nAvailable tables ({len(tables)}):')
    for table in sorted(tables):
        print(f'  - {table}')
    
    print()
    if 'scans' in tables:
        print('✓ scans table EXISTS')
        columns = inspector.get_columns('scans')
        print(f'  Columns ({len(columns)}):')
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f'    - {col["name"]}: {col["type"]} ({nullable})')
        
        # Check indexes
        indexes = inspector.get_indexes('scans')
        print(f'  Indexes ({len(indexes)}):')
        for idx in indexes:
            print(f'    - {idx["name"]}: {idx["column_names"]}')
    else:
        print('✗ scans table DOES NOT EXIST - migration needs to be applied')
        
except Exception as e:
    print(f'✗ Connection failed: {type(e).__name__}')
    print(f'  {e}')
