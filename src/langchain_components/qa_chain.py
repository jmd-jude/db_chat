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
from dotenv import load_dotenv
import sqlparse

# Load environment variables
load_dotenv(override=True)

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

def get_openai_client():
    """Initialize OpenAI client with API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
    
    # Log API key details (for debugging)
    logging.info(f"API Key found: {bool(api_key)}")
    logging.info(f"API Key length: {len(api_key)}")
    logging.info(f"API Key prefix: {api_key[:7]}...")
    
    return ChatOpenAI(
        api_key=api_key,
        model="gpt-3.5-turbo",
        temperature=0
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
    """Load schema configuration from file."""
    try:
        config_path = os.path.join('schema_configs', f'{db_type}_schema_config.yaml')
        if not os.path.exists(config_path):
            config_path = 'schema_config.yaml' if db_type == 'sqlite' else 'snowflake_schema_config.yaml'
        
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logging.error(f"Error loading schema config: {str(e)}")
        raise

def load_prompt_config():
    """Load prompt configuration from YAML."""
    try:
        with open('prompts.yaml', 'r') as file:
            config = yaml.safe_load(file)
            return config['prompts']['sql_generation']
    except Exception as e:
        logging.error(f"Error loading prompt config: {str(e)}")
        raise

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
    """Sanitize SQL query using sqlparse for better reliability."""
    # Remove SQL code blocks if present
    query = re.sub(r'```sql|```', '', query)
    
    # Format the SQL properly using sqlparse
    formatted = sqlparse.format(
        query,
        reindent=True,
        keyword_case='upper',
        identifier_case='lower',
        strip_comments=True,
        use_space_around_operators=True
    )
    
    # Handle database-specific date functions
    if db_type == "snowflake":
        # Convert SQLite date functions to Snowflake equivalents
        formatted = formatted.replace(
            "strftime('%Y'", "DATE_PART('YEAR'"
        ).replace(
            "strftime('%Y-%m'", "DATE_TRUNC('MONTH'"
        ).replace(
            "strftime('%Y-%m-%d'", "DATE_TRUNC('DAY'"
        )
    
    return formatted.strip()

def create_sql_generation_prompt(db_type="sqlite", chat_history=None):
    """Create prompt template using configuration from YAML."""
    # Load configurations
    config = load_schema_config(db_type)
    prompt_config = load_prompt_config()
    
    # Get database-specific rules if they exist
    query_rules = prompt_config.get('database_specific', {}).get(db_type, {}).get('query_rules', prompt_config['query_rules'])
    formatted_rules = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(query_rules))
    
    # Format schema and example contexts
    schema_context = format_schema_context(config)
    example_queries = format_example_queries(config)
    
    # Format history context
    history_context = ""
    if chat_history:
        history_text = "\n".join([
            f"Q: {h['question']}\nSQL: {h['query']}\nResult: {h['result']}"
            for h in chat_history
        ])
        history_context = f"\nRecent Query History:\n{history_text}\n"
    
    # Fill in the template
    prompt_text = prompt_config['template'].format(
        base_role=prompt_config['base_role'].format(database_type=config['database_config']['type']),
        main_instruction=prompt_config['main_instruction'],
        schema_context=schema_context,
        example_queries=example_queries,
        history_context=history_context,
        formatted_rules=formatted_rules,
        question="{question}"  # Left for ChatPromptTemplate to fill
    )
    
    return ChatPromptTemplate.from_template(prompt_text)

memory_manager = QueryMemoryManager()

def generate_dynamic_query(question: str, thread_id: str = "default", db_type: str = "sqlite"):
    """Generate SQL query from natural language question."""
    try:
        llm = get_openai_client()
        chat_history = memory_manager.get_chat_history(thread_id)
        prompt = create_sql_generation_prompt(db_type, chat_history)
        
        messages = prompt.format_messages(question=question)
        response = llm.invoke(messages)
        return sanitize_sql(response.content, db_type)
    except Exception as e:
        logging.error(f"Error generating query: {str(e)}")
        raise

def execute_dynamic_query(query: str, question: str = None, thread_id: str = "default", db_type: str = "sqlite"):
    """Execute generated SQL query and return results."""
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
