import sqlite3
import yaml
from datetime import datetime
import sys
import os

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
    
    # Add query guidelines
    schema_config['query_guidelines'] = {
        'tips': [
            'Use proper table aliases in joins',
            'Include appropriate WHERE clauses',
            'Use proper date formatting for timestamp columns',
            'Consider using aggregation functions where appropriate'
        ],
        'validation': [
            'Ensure column references are fully qualified (table.column)',
            'Include proper type casting for numerical operations',
            'Use COALESCE for handling NULL values in calculations'
        ]
    }
    
    conn.close()
    return schema_config

def save_schema_config(config, output_path):
    """Save the schema configuration to a YAML file."""
    with open(output_path, 'w') as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)

def main():
    if len(sys.argv) < 2:
        print("Usage: python schema_inspector.py <database_path> [output_path]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'schema_config.yaml'
    
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)
    
    try:
        config = inspect_sqlite_database(db_path)
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
