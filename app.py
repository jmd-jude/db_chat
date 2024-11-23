import streamlit as st
import os
from dotenv import load_dotenv
import yaml
from src.schema_manager import SchemaManager
from src.database.schema_inspector import inspect_database
from src.langchain_components.qa_chain import generate_dynamic_query, execute_dynamic_query
import pandas as pd
import importlib.util
import traceback

# Load environment variables
load_dotenv(override=True)

# Feature flags
SHOW_SCHEMA_EDITOR = False  # Set to True to show schema editor in sidebar

# Initialize schema manager
schema_manager = SchemaManager()

def is_snowflake_available():
    """Check if Snowflake dependencies are installed."""
    snowflake_connector = importlib.util.find_spec("snowflake.connector")
    snowflake_sqlalchemy = importlib.util.find_spec("snowflake.sqlalchemy")
    return snowflake_connector is not None and snowflake_sqlalchemy is not None

def check_api_key():
    """Check if OpenAI API key is configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        st.stop()
    
    if SHOW_SCHEMA_EDITOR:
        # Debug information (will be removed in production)
        st.sidebar.write("API Key Status:")
        st.sidebar.write(f"Key found: {bool(api_key)}")
        st.sidebar.write(f"Key length: {len(api_key) if api_key else 0}")
        st.sidebar.write(f"Key prefix: {api_key[:7]}..." if api_key else "No key")

def check_snowflake_config():
    """Check Snowflake configuration if needed."""
    required_vars = [
        'SNOWFLAKE_ACCOUNT',
        'SNOWFLAKE_USER',
        'SNOWFLAKE_PASSWORD',
        'SNOWFLAKE_DATABASE',
        'SNOWFLAKE_WAREHOUSE',
        'SNOWFLAKE_SCHEMA'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    return len(missing_vars) == 0, missing_vars

def setup_database_config():
    """Initial database setup and configuration."""
    # Check Snowflake availability
    snowflake_available = is_snowflake_available()
    
    # Database selection
    db_options = ["sqlite"]
    if snowflake_available:
        db_options.append("snowflake")
    
    # Create columns for layout
    col1, col2 = st.columns([2, 3])
    
    with col1:
        db_type = st.selectbox(
            "Select Data Source",
            db_options,
            help="Choose your database type"
        )
    
    # Show Snowflake availability status
    if not snowflake_available:
        with col2:
            st.info("Snowflake support is not available. Install snowflake-connector-python and snowflake-sqlalchemy to enable Snowflake queries.")
    
    # Check configuration based on database type
    if db_type == "snowflake":
        is_valid, missing_vars = check_snowflake_config()
        if not is_valid:
            st.error(f"Missing Snowflake configuration: {', '.join(missing_vars)}")
            st.info("Please set these environment variables to use Snowflake.")
            st.stop()
    
    return db_type

def load_or_create_schema(db_type):
    """Load existing schema config or create new one."""
    config = schema_manager.load_config(db_type)
    
    if not config:
        st.info("Generating schema configuration...")
        try:
            if db_type == "sqlite":
                config = inspect_database(db_type="sqlite", db_path="sample.db")
            else:
                config = inspect_database(
                    db_type="snowflake",
                    account=os.getenv('SNOWFLAKE_ACCOUNT'),
                    user=os.getenv('SNOWFLAKE_USER'),
                    password=os.getenv('SNOWFLAKE_PASSWORD'),
                    database=os.getenv('SNOWFLAKE_DATABASE'),
                    warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
                    schema=os.getenv('SNOWFLAKE_SCHEMA')
                )
            schema_manager.save_config(db_type, config)
            st.success("Schema configuration generated successfully!")
        except Exception as e:
            st.error(f"Error generating schema configuration: {str(e)}")
            st.error("Full error details:")
            st.exception(e)
            st.stop()
    
    return config

def schema_editor(db_type, config):
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
                db_type,
                description,
                concepts_text.split('\n') if concepts_text else []
            )
            st.success("Business context updated!")
        
        # Table Descriptions
        st.subheader("Table Descriptions")
        selected_table = st.selectbox(
            "Select Table",
            schema_manager.get_tables(db_type)
        )
        
        if selected_table:
            table_desc = st.text_area(
                f"Description for {selected_table}",
                value=config['tables'][selected_table].get('description', ''),
                key=f"table_desc_{selected_table}"
            )
            
            if st.button(f"Update {selected_table} Description"):
                schema_manager.update_table_description(db_type, selected_table, table_desc)
                st.success(f"Updated description for {selected_table}!")
            
            # Field Descriptions
            st.subheader("Field Descriptions")
            selected_field = st.selectbox(
                "Select Field",
                schema_manager.get_fields(db_type, selected_table)
            )
            
            if selected_field:
                field_desc = st.text_area(
                    f"Description for {selected_field}",
                    value=config['tables'][selected_table]['fields'][selected_field].get('description', ''),
                    key=f"field_desc_{selected_table}_{selected_field}"
                )
                
                if st.button(f"Update {selected_field} Description"):
                    schema_manager.update_field_description(
                        db_type, selected_table, selected_field, field_desc
                    )
                    st.success(f"Updated description for {selected_field}!")

def main():
    st.title("Talk with Your Data")
    
    # Check OpenAI API key with detailed feedback
    check_api_key()
    
    # Setup database configuration
    db_type = setup_database_config()
    
    # Load or create schema configuration
    config = load_or_create_schema(db_type)
    
    # Schema editor in sidebar (only if enabled)
    if SHOW_SCHEMA_EDITOR:
        schema_editor(db_type, config)
    
    # Main query interface
    st.header("Ask Questions About Your Data")
    
    with st.expander("Example Questions", expanded=False):
        st.markdown("""
           **Simple Questions:**
            - What are our total sales by product category?
            - How are different payment methods performing in terms of order value?
            - Where are our customers located across states?

            **Intermediate Questions:**
            - Which states are generating the highest order values?
            - Who are our most frequent buyers and what's their total spend?
            - How do customers prefer to pay across different months?

            **Complex Questions:**
            - How long does it take us to deliver different product categories?
            - Break down our revenue by state and payment type
            - How are our average order values trending over time?
           """)
    
    # Query input using chat_input
    if question := st.chat_input("Ask a question about your data..."):
        try:
            with st.spinner("Generating query..."):
                # Generate SQL query
                sql_query = generate_dynamic_query(question, db_type=db_type)
                
                # Show the generated SQL
                with st.expander("Generated SQL", expanded=True):
                    st.code(sql_query, language="sql")
                
                # Execute query and show results
                results = execute_dynamic_query(sql_query, question, db_type=db_type)
                
                if isinstance(results, pd.DataFrame):
                    st.dataframe(results)
                else:
                    st.error(f"Error executing query: {results}")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.error("Full error details:")
            st.exception(e)

if __name__ == "__main__":
    main()
