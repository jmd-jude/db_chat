import sqlite3
import pandas as pd

# Connect to the database
conn = sqlite3.connect('sample.db')

# Get all table names
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)

# Export each table to CSV
for table_name in tables['name']:
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    df.to_csv(f"{table_name}.csv", index=False)
    print(f"Exported {table_name} to {table_name}.csv")

conn.close()
