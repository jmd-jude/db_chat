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
SHOW_SCHEMA_EDITOR = True  # Set to True to show schema editor in sidebar

# Initialize schema manager
schema_manager = SchemaManager()

def check_api_key():
    """Check if OpenAI API key is configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        st.stop()

def check_snowflake_config():
    """Check Snowflake configuration."""
    required_vars = [
        'SNOWFLAKE_ACCOUNT',
        'SNOWFLAKE_USER',
        'SNOWFLAKE_PASSWORD',
        'SNOWFLAKE_DATABASE',
        'SNOWFLAKE_WAREHOUSE',
        'SNOWFLAKE_SCHEMA'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        st.error(f"Missing Snowflake configuration: {', '.join(missing_vars)}")
        st.info("Please set these environment variables to use Snowflake.")
        st.stop()

def load_or_create_schema():
    """Load existing schema config or create new one."""
    config = schema_manager.load_config("snowflake")
    
    if not config:
        st.info("Generating schema configuration...")
        try:
            config = inspect_database(
                db_type="snowflake",
                account=os.getenv('SNOWFLAKE_ACCOUNT'),
                user=os.getenv('SNOWFLAKE_USER'),
                password=os.getenv('SNOWFLAKE_PASSWORD'),
                database=os.getenv('SNOWFLAKE_DATABASE'),
                warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
                schema=os.getenv('SNOWFLAKE_SCHEMA')
            )
            schema_manager.save_config("snowflake", config)
            st.success("Schema configuration generated successfully!")
        except Exception as e:
            st.error(f"Error generating schema configuration: {str(e)}")
            st.error("Full error details:")
            st.exception(e)
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

def main():
    st.title("Talk with Your Data")
    
    # Check OpenAI API key with detailed feedback
    check_api_key()
    
    # Check Snowflake configuration
    check_snowflake_config()
    
    # Load or create schema configuration
    config = load_or_create_schema()
    
    # Schema editor in sidebar (only if enabled)
    if SHOW_SCHEMA_EDITOR:
        schema_editor(config)
    
    # Main query interface
    st.header("Ask Questions About Your Data")
    
    with st.expander("Example Questions", expanded=False):
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
            st.error(f"Error: {str(e)}")
            st.error("Full error details:")
            st.exception(e)

if __name__ == "__main__":
    main()
