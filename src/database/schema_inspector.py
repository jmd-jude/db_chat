import sqlite3
import yaml
from datetime import datetime
import sys
import os
import pandas as pd
from sqlalchemy import create_engine
from snowflake.sqlalchemy import URL

def inspect_sqlite_database(db_path):
    """
    Inspect a SQLite database and generate a schema configuration.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema_config = {
        'business_context': {
            'description': 'Auto-generated schema configuration',
            'key_concepts': [
                'Generated from database inspection',
                'Please update with business-specific concepts'
            ]
        },
        'database_config': {
            'type': 'sqlite',
            'date_functions': {
                'year': "strftime('%Y', {column})",
                'month': "strftime('%Y-%m', {column})",
                'date': "strftime('%Y-%m-%d', {column})"
            },
            'date_formats': {
                'literal': 'YYYY-MM-DD',
                'year': 'YYYY',
                'month': 'YYYY-MM'
            },
            'example_patterns': [
                {
                    'description': 'Monthly aggregation',
                    'pattern': "strftime('%Y-%m', {column}) AS {alias}"
                },
                {
                    'description': 'Year comparison',
                    'pattern': "strftime('%Y', {column}) = '{year}'"
                },
                {
                    'description': 'Date range',
                    'pattern': "{column} BETWEEN '{start_date}' AND '{end_date}'"
                }
            ]
        },
        'tables': {}
    }
    
    # Inspect each table
    for table_name in tables:
        table_name = table_name[0]
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        # Get foreign key info
        cursor.execute(f"PRAGMA foreign_key_list({table_name});")
        foreign_keys = cursor.fetchall()
        
        table_info = {
            'description': f'Table containing {table_name} data',
            'fields': {}
        }
        
        # Process columns
        for col in columns:
            col_id, col_name, col_type, not_null, default_value, is_pk = col
            
            field_info = {
                'type': col_type.upper(),
                'description': f'{col_name} field',
            }
            
            if is_pk:
                field_info['is_key'] = True
            
            # Check if this column is a foreign key
            for fk in foreign_keys:
                if fk[3] == col_name:  # fk[3] is the column name
                    field_info['foreign_key'] = f"{fk[2]}.{fk[4]}"  # fk[2] is referenced table, fk[4] is referenced column
            
            table_info['fields'][col_name] = field_info
        
        # Add relationships based on foreign keys
        if foreign_keys:
            table_info['relationships'] = []
            for fk in foreign_keys:
                relationship = {
                    'table': fk[2],  # Referenced table
                    'type': 'many_to_one',  # Assume many-to-one by default
                    'join_fields': [fk[3], fk[4]]  # Local and referenced columns
                }
                table_info['relationships'].append(relationship)
        
        schema_config['tables'][table_name] = table_info
    
    conn.close()
    return schema_config

def inspect_snowflake_database(conn):
    """
    Inspect a Snowflake database and generate a schema configuration.
    """
    schema_config = {
        'business_context': {
            'description': 'Auto-generated schema configuration for Snowflake database',
            'key_concepts': [
                'Generated from Snowflake database inspection',
                'Please update with business-specific concepts'
            ]
        },
        'database_config': {
            'type': 'snowflake',
            'date_functions': {
                'year': "DATE_PART('YEAR', {column})",
                'month': "DATE_TRUNC('MONTH', {column})",
                'date': "DATE_TRUNC('DAY', {column})"
            },
            'date_formats': {
                'literal': 'YYYY-MM-DD',
                'year': 'YYYY',
                'month': 'YYYY-MM'
            },
            'example_patterns': [
                {
                    'description': 'Monthly aggregation',
                    'pattern': "DATE_TRUNC('MONTH', {column}) AS {alias}"
                },
                {
                    'description': 'Year comparison',
                    'pattern': "DATE_PART('YEAR', {column}) = {year}"
                },
                {
                    'description': 'Date range',
                    'pattern': "{column} BETWEEN '{start_date}' AND '{end_date}'"
                }
            ]
        },
        'tables': {}
    }
    
    # Get tables
    tables_query = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = CURRENT_SCHEMA()
    AND TABLE_TYPE = 'BASE TABLE'
    """
    tables = pd.read_sql(tables_query, conn)
    
    # Inspect each table
    for table_name in tables['TABLE_NAME']:
        # Get column info
        columns_query = f"""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            ORDINAL_POSITION,
            CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION,
            NUMERIC_SCALE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        columns = pd.read_sql(columns_query, conn)
        
        # Get primary keys
        pk_query = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_NAME = '{table_name}'
        AND CONSTRAINT_NAME LIKE 'PK_%'
        """
        primary_keys = pd.read_sql(pk_query, conn)
        
        # Get foreign keys
        fk_query = f"""
        SELECT 
            CONSTRAINT_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_NAME = '{table_name}'
        AND CONSTRAINT_NAME LIKE 'FK_%'
        """
        foreign_keys = pd.read_sql(fk_query, conn)
        
        table_info = {
            'description': f'Table containing {table_name} data',
            'fields': {}
        }
        
        # Process columns
        for _, col in columns.iterrows():
            field_info = {
                'type': col['DATA_TYPE'].upper(),
                'description': f'{col["COLUMN_NAME"]} field',
                'nullable': col['IS_NULLABLE'] == 'YES'
            }
            
            # Add primary key info
            if not primary_keys.empty and col['COLUMN_NAME'] in primary_keys['COLUMN_NAME'].values:
                field_info['is_key'] = True
            
            # Add foreign key info
            if not foreign_keys.empty:
                fk_info = foreign_keys[foreign_keys['COLUMN_NAME'] == col['COLUMN_NAME']]
                if not fk_info.empty:
                    field_info['foreign_key'] = f"{fk_info['REFERENCED_TABLE_NAME'].iloc[0]}.{fk_info['REFERENCED_COLUMN_NAME'].iloc[0]}"
            
            table_info['fields'][col['COLUMN_NAME']] = field_info
        
        # Add relationships based on foreign keys
        if not foreign_keys.empty:
            table_info['relationships'] = []
            for _, fk in foreign_keys.iterrows():
                relationship = {
                    'table': fk['REFERENCED_TABLE_NAME'],
                    'type': 'many_to_one',
                    'join_fields': [fk['COLUMN_NAME'], fk['REFERENCED_COLUMN_NAME']]
                }
                table_info['relationships'].append(relationship)
        
        schema_config['tables'][table_name] = table_info
    
    return schema_config

def save_schema_config(config, output_path):
    """Save the schema configuration to a YAML file."""
    with open(output_path, 'w') as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)

def inspect_database(db_type="sqlite", **connection_params):
    """
    Inspect a database and generate a schema configuration.
    Supports both SQLite and Snowflake databases.
    """
    if db_type == "sqlite":
        if 'db_path' not in connection_params:
            raise ValueError("db_path is required for SQLite database inspection")
        return inspect_sqlite_database(connection_params['db_path'])
    
    elif db_type == "snowflake":
        required_params = ['account', 'user', 'password', 'database', 'warehouse', 'schema']
        missing_params = [param for param in required_params if param not in connection_params]
        if missing_params:
            raise ValueError(f"Missing required Snowflake connection parameters: {', '.join(missing_params)}")
        
        engine = create_engine(URL(
            account=connection_params['account'],
            user=connection_params['user'],
            password=connection_params['password'],
            database=connection_params['database'],
            warehouse=connection_params['warehouse'],
            schema=connection_params['schema']
        ))
        
        with engine.connect() as conn:
            return inspect_snowflake_database(conn)
    
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python schema_inspector.py <database_type> [output_path] [connection_params]")
        print("Example for SQLite: python schema_inspector.py sqlite sample.db schema_config.yaml")
        print("Example for Snowflake: python schema_inspector.py snowflake snowflake_schema_config.yaml account=xyz user=abc ...")
        sys.exit(1)
    
    db_type = sys.argv[1].lower()
    output_path = sys.argv[2] if len(sys.argv) > 2 else f'{db_type}_schema_config.yaml'
    
    try:
        if db_type == "sqlite":
            if len(sys.argv) < 3:
                print("Error: SQLite database path is required")
                sys.exit(1)
            db_path = sys.argv[2]
            output_path = sys.argv[3] if len(sys.argv) > 3 else 'schema_config.yaml'
            
            if not os.path.exists(db_path):
                print(f"Error: Database file '{db_path}' not found.")
                sys.exit(1)
            
            config = inspect_database(db_type="sqlite", db_path=db_path)
        
        elif db_type == "snowflake":
            # Parse connection parameters
            connection_params = {}
            for param in sys.argv[3:]:
                key, value = param.split('=')
                connection_params[key] = value
            
            config = inspect_database(db_type="snowflake", **connection_params)
        
        else:
            print(f"Error: Unsupported database type '{db_type}'")
            sys.exit(1)
        
        save_schema_config(config, output_path)
        print(f"Schema configuration has been saved to {output_path}")
        print("\nNote: Please review and update the following in the generated config:")
        print("1. Business context description and key concepts")
        print("2. Table and field descriptions")
        print("3. Relationship types (currently defaults to many_to_one)")
        print("4. Query guidelines and tips specific to your data")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
