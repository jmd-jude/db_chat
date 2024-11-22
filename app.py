import streamlit as st
# Must be the first Streamlit command
st.set_page_config(initial_sidebar_state="collapsed")

import os
from dotenv import load_dotenv
import yaml
import pandas as pd
import importlib.util
import traceback
import sys
from pathlib import Path
import glob
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Now import our local modules
from src.schema_manager import SchemaManager
from src.database.schema_inspector import inspect_database
from src.langchain_components.qa_chain import generate_dynamic_query, execute_dynamic_query, memory_manager

# Load environment variables - only in local development
if os.path.exists(".env"):
    load_dotenv(override=True)

# Feature flags
SHOW_SCHEMA_EDITOR = False  # Set to False to hide schema editor in sidebar

# Initialize schema manager
schema_manager = SchemaManager()

def get_available_schema_configs():
    """Get list of available schema configuration files."""
    config_files = glob.glob("schema_configs/*_schema_config*.yaml")
    return [os.path.basename(f) for f in config_files]

def get_snowflake_credentials():
    """Get Snowflake credentials from environment or streamlit secrets."""
    try:
        # Try to get from streamlit secrets first (for cloud deployment)
        account = st.secrets.snowflake.account
        # Remove any duplicate .snowflakecomputing.com
        if '.snowflakecomputing.com' in account:
            account = account.replace('.snowflakecomputing.com', '')
        
        return {
            'account': account,
            'user': st.secrets.snowflake.user,
            'password': st.secrets.snowflake.password,
            'database': st.secrets.snowflake.database,
            'warehouse': st.secrets.snowflake.warehouse,
            'schema': st.secrets.snowflake.schema
        }
    except Exception:
        # Fall back to environment variables (for local development)
        account = os.getenv('SNOWFLAKE_ACCOUNT', '')
        if '.snowflakecomputing.com' in account:
            account = account.replace('.snowflakecomputing.com', '')
            
        return {
            'account': account,
            'user': os.getenv('SNOWFLAKE_USER'),
            'password': os.getenv('SNOWFLAKE_PASSWORD'),
            'database': os.getenv('SNOWFLAKE_DATABASE'),
            'warehouse': os.getenv('SNOWFLAKE_WAREHOUSE'),
            'schema': os.getenv('SNOWFLAKE_SCHEMA')
        }

def check_api_key():
    """Check if OpenAI API key is configured."""
    try:
        api_key = st.secrets.openai.api_key
    except Exception:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY in environment variables or Streamlit secrets.")
        st.stop()

def check_snowflake_config():
    """Check Snowflake configuration."""
    creds = get_snowflake_credentials()
    missing_vars = [key for key, value in creds.items() if not value]
    
    if missing_vars:
        st.error(f"Missing Snowflake configuration: {', '.join(missing_vars)}")
        st.info("Please set these values in Streamlit secrets or environment variables.")
        st.stop()

def load_or_create_schema(config_file=None):
    """Load existing schema config or create new one."""
    if config_file:
        try:
            with open(os.path.join("schema_configs", config_file), 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            st.error(f"Error loading schema config: {str(e)}")
            st.stop()
    
    config = schema_manager.load_config("snowflake")
    
    if not config:
        st.info("Generating schema configuration...")
        try:
            creds = get_snowflake_credentials()
            config = inspect_database(
                db_type="snowflake",
                **creds
            )
            schema_manager.save_config("snowflake", config)
            st.success("Schema configuration generated successfully!")
        except Exception as e:
            st.error("Error connecting to Snowflake. Please check your credentials and network settings.")
            st.error("If you're using Streamlit Cloud, ensure all secrets are properly configured.")
            st.error(f"Error details: {str(e)}")
            st.stop()
    
    return config

def schema_editor(config):
    """Simple schema configuration editor."""
    with st.sidebar.expander("Edit Schema Configuration"):
        # Business Context
        st.subheader("Business Context")
        description = st.text_area(
            "Business Description",
            value=config.get('business_context', {}).get('description', ''),
            key="business_desc"
        )
        
        # Key Concepts
        concepts = config.get('business_context', {}).get('key_concepts', [])
        concepts_text = st.text_area(
            "Key Business Concepts (one per line)",
            value='\n'.join(concepts) if concepts else '',
            key="key_concepts"
        )
        
        if st.button("Update Business Context"):
            schema_manager.update_business_context(
                "snowflake",
                description,
                concepts_text.split('\n') if concepts_text else []
            )
            st.success("Business context updated!")
        
        # Table Descriptions
        st.subheader("Table Descriptions")
        selected_table = st.selectbox(
            "Select Table",
            schema_manager.get_tables("snowflake")
        )
        
        if selected_table:
            table_desc = st.text_area(
                f"Description for {selected_table}",
                value=config['tables'][selected_table].get('description', ''),
                key=f"table_desc_{selected_table}"
            )
            
            if st.button(f"Update {selected_table} Description"):
                schema_manager.update_table_description("snowflake", selected_table, table_desc)
                st.success(f"Updated description for {selected_table}!")
            
            # Field Descriptions
            st.subheader("Field Descriptions")
            selected_field = st.selectbox(
                "Select Field",
                schema_manager.get_fields("snowflake", selected_table)
            )
            
            if selected_field:
                field_desc = st.text_area(
                    f"Description for {selected_field}",
                    value=config['tables'][selected_table]['fields'][selected_field].get('description', ''),
                    key=f"field_desc_{selected_table}_{selected_field}"
                )
                
                if st.button(f"Update {selected_field} Description"):
                    schema_manager.update_field_description(
                        "snowflake", selected_table, selected_field, field_desc
                    )
                    st.success(f"Updated description for {selected_field}!")

def display_chat_history():
    """Display chat history in a clean, collapsible format."""
    history = memory_manager.get_chat_history()
    if not history:
        return

    with st.expander("Recent Questions", expanded=False):
        for i, interaction in enumerate(reversed(history)):  # Show most recent first
            # Format timestamp
            timestamp = datetime.fromisoformat(interaction['timestamp'])
            time_str = timestamp.strftime("%I:%M %p")  # e.g., "2:30 PM"
            
            # Create columns for timestamp and question
            cols = st.columns([1, 4])
            with cols[0]:
                st.text(time_str)
            with cols[1]:
                st.markdown(f"**Q:** {interaction['question']}")
                st.caption("SQL Query:")
                st.code(interaction['query'], language="sql")
            
            # Add a subtle divider between interactions
            if i < len(history) - 1:
                st.divider()

def main():
    st.title("Talk with Your Data")
    
    # Check OpenAI API key with detailed feedback
    check_api_key()
    
    # Check Snowflake configuration
    check_snowflake_config()
    
    # Schema config selection
    available_configs = get_available_schema_configs()
    selected_config = st.sidebar.selectbox(
        "Select Schema Configuration",
        available_configs,
        help="Choose different schema configurations to experiment with AI responses"
    )
    
    # Example questions in sidebar
    with st.sidebar.expander("Example Questions", expanded=False):
        st.markdown("""
           **Simple Questions:**
            - How many customers do we have?
            - What's the total value of all orders?
            - Show me the distribution of orders by nation

            **Intermediate Questions:**
            - What's the average order value by region?
            - Who are our top 10 customers by order value?
            - Show order trends over time by region

            **Complex Questions:**
            - What's the average delivery time by product category?
            - Show me customer order patterns across different regions
            - Calculate market share by supplier within each region
           """)
    
    # Load selected schema configuration
    config = load_or_create_schema(selected_config)
    
    # Schema editor in sidebar (only if enabled)
    if SHOW_SCHEMA_EDITOR:
        schema_editor(config)
    
    # Main query interface
    st.header("Ask Questions About Your Data")
    
    # Display chat history before the input
    display_chat_history()
    
    # Query input using chat_input
    if question := st.chat_input("Ask a question about your data..."):
        try:
            with st.spinner("Generating query..."):
                # Generate SQL query
                sql_query = generate_dynamic_query(question)
                
                # Show the generated SQL
                with st.expander("Generated SQL", expanded=True):
                    st.code(sql_query, language="sql")
                
                # Execute query and show results
                results = execute_dynamic_query(sql_query, question)
                
                if isinstance(results, pd.DataFrame):
                    st.dataframe(results)
                else:
                    st.error(f"Error executing query: {results}")
        
        except Exception as e:
            st.error("An error occurred while processing your question.")
            st.error(f"Error details: {str(e)}")

if __name__ == "__main__":
    main()
