import sqlite3
import pandas as pd

def generate_sql_query(table, fields, where=None, order_by=None, limit=None):
    """Generate a SQL query based on the provided parameters."""
    # Start with basic SELECT
    sql = f"SELECT {', '.join(fields)} FROM {table}"
    
    # Add WHERE clause if provided
    if where:
        sql += f" WHERE {where}"
    
    # Add ORDER BY if provided
    if order_by:
        sql += f" ORDER BY {order_by}"
    
    # Add LIMIT if provided
    if limit:
        sql += f" LIMIT {limit}"
    
    return sql

def execute_query(sql, db_path):
    """Execute a SQL query and return results as a pandas DataFrame."""
    conn = sqlite3.connect(db_path)
    try:
        # Execute query and fetch results into DataFrame
        df = pd.read_sql_query(sql, conn)
        return df
    finally:
        conn.close()

def validate_query(sql, schema_config):
    """Validate a SQL query against the schema configuration."""
    # TODO: Implement query validation using schema config
    # - Check that referenced tables exist
    # - Check that referenced columns exist
    # - Validate data types in WHERE clause
    # - Check foreign key references
    pass
