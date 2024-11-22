from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
import sqlite3
import pandas as pd
import yaml
import re
from collections import defaultdict
from datetime import datetime
import logging
import os
import json
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine

# Set up logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f'chat_history_{datetime.now().strftime("%Y%m%d")}.log')),
        logging.StreamHandler()
    ]
)

class DatabaseConnection:
    def __init__(self, db_type="sqlite"):
        self.db_type = db_type
        self.engine = None
        self.connection = None
    
    def get_connection(self):
        if self.db_type == "sqlite":
            return sqlite3.connect('sample.db')
        elif self.db_type == "snowflake":
            if not self.engine:
                self.engine = create_engine(URL(
                    account=os.getenv('SNOWFLAKE_ACCOUNT'),
                    user=os.getenv('SNOWFLAKE_USER'),
                    password=os.getenv('SNOWFLAKE_PASSWORD'),
                    database=os.getenv('SNOWFLAKE_DATABASE'),
                    warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
                    schema=os.getenv('SNOWFLAKE_SCHEMA')
                ))
            return self.engine.connect()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

class QueryMemoryManager:
    def __init__(self, window_size=5):
        self.history = defaultdict(list)
        self.window_size = window_size
    
    def get_chat_history(self, thread_id: str = "default"):
        return self.history[thread_id][-self.window_size:] if self.history[thread_id] else []
    
    def save_interaction(self, thread_id: str, question: str, query: str, result):
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'thread_id': thread_id,
            'question': question,
            'query': query,
            'result': str(result)
        }
        self.history[thread_id].append(interaction)
        
        # Log the interaction
        logging.info(json.dumps(interaction, indent=2))

def load_schema_config(db_type="sqlite"):
    config_file = 'schema_config.yaml' if db_type == 'sqlite' else 'snowflake_schema_config.yaml'
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def format_schema_context(config):
    """Convert schema config into prompt-friendly format"""
    context = [f"Business Context: {config['business_context']['description']}"]
    
    concepts = "\n".join(f"- {c}" for c in config['business_context']['key_concepts'])
    context.append(f"Key Business Concepts:\n{concepts}")
    
    for table_name, table_info in config['tables'].items():
        context.append(f"\nTable: {table_name}")
        context.append(f"Description: {table_info['description']}")
        
        fields = []
        for field_name, field_info in table_info['fields'].items():
            field_desc = f"- {field_name} ({field_info['type']}): {field_info['description']}"
            if field_info.get('is_key'):
                field_desc += " (Primary Key)"
            if field_info.get('foreign_key'):
                field_desc += f" (Foreign Key -> {field_info['foreign_key']})"
            fields.append(field_desc)
        context.append("Fields:\n" + "\n".join(fields))
        
        if 'relationships' in table_info:
            rels = []
            for rel in table_info['relationships']:
                rels.append(f"- {rel['type']} relationship with {rel['table']} on {rel['join_fields']}")
            context.append("Relationships:\n" + "\n".join(rels))
    
    if 'query_guidelines' in config:
        tips = "\n".join(f"- {tip}" for tip in config['query_guidelines']['tips'])
        context.append(f"\nQuery Guidelines:\n{tips}")
    
    return "\n\n".join(context)

def format_example_queries(config):
    """Format example queries from the configuration"""
    db_config = config.get('database_config', {})
    if not db_config or 'example_queries' not in db_config:
        return ""

    examples = ["\nExample Queries:"]
    for example in db_config['example_queries']:
        examples.append(f"\n{example['description']}:")
        examples.append(example['query'].strip())
    
    return "\n".join(examples)

def sanitize_sql(query, db_type="sqlite"):
    """Sanitize SQL query using database-specific patterns"""
    # Remove SQL code blocks
    query = re.sub(r'```sql|```', '', query)
    
    if db_type == "sqlite":
        # Fix date literals - ensure proper quoting
        query = re.sub(r'(\d{4}-\d{2}-\d{2})', r"'\1'", query)
        query = re.sub(r'(\d{4}-\d{2})', r"'\1'", query)
    elif db_type == "snowflake":
        # Convert SQLite date functions to Snowflake equivalents
        query = re.sub(r"strftime\('%Y', ([^)]+)\)", r"DATE_PART('YEAR', \1)", query)
        query = re.sub(r"strftime\('%Y-%m', ([^)]+)\)", r"DATE_TRUNC('MONTH', \1)", query)
        query = re.sub(r"strftime\('%Y-%m-%d', ([^)]+)\)", r"DATE_TRUNC('DAY', \1)", query)
    
    # Fix spacing around operators
    query = re.sub(r'\s*([=<>])\s*', r' \1 ', query)
    
    return query.strip()

def create_sql_generation_prompt(db_type="sqlite", chat_history=None):
    config = load_schema_config(db_type)
    schema_context = format_schema_context(config)
    example_queries = format_example_queries(config)
    
    history_context = ""
    if chat_history:
        history_text = "\n".join([
            f"Q: {h['question']}\nSQL: {h['query']}\nResult: {h['result']}"
            for h in chat_history
        ])
        history_context = f"\nRecent Query History:\n{history_text}\n"
    
    template = f"""You are an expert SQL query generator for a {config['database_config']['type']} database.
    Given the schema, business context, and query history below, generate a SQL query to answer the question.

    {schema_context}
    
    {example_queries}
    
    {history_context}
    Question: {{question}}

    Return only the SQL query, nothing else.
    Ensure the query:
    1. Uses proper table aliases when joining
    2. Uses proper date formatting for timestamps
    3. Uses proper column names as defined in the schema
    4. Always includes column aliases for aggregated fields
    5. Always uses table aliases in column references
    6. Groups results appropriately when using aggregations

    SQL Query:"""
    
    return ChatPromptTemplate.from_template(template)

memory_manager = QueryMemoryManager()

def generate_dynamic_query(question: str, thread_id: str = "default", db_type: str = "sqlite"):
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    chat_history = memory_manager.get_chat_history(thread_id)
    prompt = create_sql_generation_prompt(db_type, chat_history)
    
    messages = prompt.format_messages(question=question)
    response = llm.invoke(messages)
    return sanitize_sql(response.content, db_type)

def execute_dynamic_query(query: str, question: str = None, thread_id: str = "default", db_type: str = "sqlite"):
    db = DatabaseConnection(db_type)
    conn = db.get_connection()
    try:
        # Execute with pandas
        result = pd.read_sql_query(query, conn)
        
        if question:
            memory_manager.save_interaction(thread_id, question, query, result)
        return result
    except Exception as e:
        error_msg = f"Error executing query: {str(e)}"
        if question:
            memory_manager.save_interaction(thread_id, question, query, error_msg)
        return error_msg
    finally:
        db.close()
