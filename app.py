import streamlit as st
import sqlite3
import pandas as pd
import yaml
from src.database.queries import StandardMetricQueries
from langchain_core.prompts import ChatPromptTemplate
from src.langchain_components.qa_chain import generate_dynamic_query, execute_dynamic_query
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import traceback
import importlib.util

# Demo mode configuration
DEMO_MODE = True  # Set to False to show all features

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
   raise ValueError("OPENAI_API_KEY environment variable not set.")

# Check if Snowflake dependencies are installed
def is_snowflake_available():
    snowflake_connector = importlib.util.find_spec("snowflake.connector")
    snowflake_sqlalchemy = importlib.util.find_spec("snowflake.sqlalchemy")
    return snowflake_connector is not None and snowflake_sqlalchemy is not None

# Load prompts from YAML
def load_prompts():
   with open('prompts.yaml', 'r') as file:
       return yaml.safe_load(file)['prompts']

def format_currency(val):
  return f"${val:,.2f}"

def format_number(val):
  return f"{val:,.0f}"

def format_percent(val):
  return f"{val:.1f}%"

def load_data():
   db_path = os.path.join(os.path.dirname(__file__), 'sample.db')
   conn = sqlite3.connect(db_path)
   queries = StandardMetricQueries()
   return {query_name: queries.execute_query(conn, query_name) 
           for query_name in dir(StandardMetricQueries) 
           if not query_name.startswith('_') and not query_name == 'execute_query'}

def generate_analysis(data, selected_prompt):
   llm = ChatOpenAI(model="gpt-4-turbo-preview")
   
   prompt = ChatPromptTemplate.from_template(selected_prompt)
   
   # Format data for prompt
   current_metrics = "\n".join([f"{k}:\n{v.to_string()}" for k,v in data.items() 
                             if not k.endswith('_TREND')])
   trend_data = "\n".join([f"{k}:\n{v.to_string()}" for k,v in data.items() 
                         if k.endswith('_TREND')])
   
   messages = prompt.format_messages(
       current_metrics=current_metrics,
       trend_data=trend_data
   )
   
   response = llm.invoke(messages)
   return response.content

def validate_snowflake_env():
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

def main():
  st.title("Talk with Your Data")
  
  if DEMO_MODE:
      tab2 = st.tabs(["Custom Query Experience"])[0]
  else:
      tab1, tab2 = st.tabs(["Standard Metrics", "Custom Query Experience"])
  
  if not DEMO_MODE:
      with tab1:
         
         # Load prompts
         prompts = load_prompts()
         
         # Create prompt selection section
         st.sidebar.header("Analysis Configuration")
         
         prompt_options = {f"{v['name']} - {v['description']}": v['template'] 
                         for v in prompts.values()}
         selected_name = st.sidebar.selectbox(
             "Select analysis type:",
             list(prompt_options.keys())
         )
         selected_prompt = prompt_options[selected_name]

         # Custom CSS to widen layout and style containers
         st.markdown("""
             <style>
             .main .block-container {
                 max-width: 1200px;
                 padding-top: 2rem;
                 padding-right: 2rem;
                 padding-left: 2rem;
                 padding-bottom: 2rem;
             }
             .stExpander {
                 min-height: 400px;
             }
             .streamlit-expanderHeader {
                 font-size: 1.2rem;
                 font-weight: 600;
             }
             div[data-testid="column"] {
                 width: calc(50% - 1rem);
                 padding: 0 1rem;
             }
             </style>
             """, unsafe_allow_html=True)

         # Load data immediately
         data = load_data()
         
         # Header and Analysis button side by side
         header_col, button_col = st.columns([4,1])
         with header_col:
             st.header("Current Performance")
         with button_col:
             st.write("")  # Spacing
             generate_button = st.button("Generate Analysis", key="generate_analysis")
         
         # Top metrics row
         col1, col2, col3 = st.columns(3)
         with col1:
             metrics = data['CUSTOMER_METRICS']
             st.metric("Total Customers", 
                      format_number(metrics['total_customers'].iloc[0]))
         with col2:
             metrics = data['SALES_OVERVIEW']
             st.metric("Total Revenue", 
                      format_currency(metrics['total_revenue'].sum()))
         with col3:
             st.metric("Avg Order Value",
                      format_currency(metrics['avg_order_value'].mean()))

         # Main content in two columns
         container = st.container()
         with container:
             left_col, right_col = st.columns(2)
             
             with left_col:
                 with st.expander("Sales Performance", expanded=True):
                     st.subheader("Category Performance")
                     st.dataframe(
                         data['CATEGORY_PERFORMANCE'],
                         height=300,
                         use_container_width=True
                     )
                     st.subheader("Payment Methods")
                     st.dataframe(
                         data['PAYMENT_METHODS'],
                         height=300,
                         use_container_width=True
                     )
                 
                 with st.expander("Customer Insights", expanded=True):
                     st.subheader("Customer Segments")
                     st.dataframe(
                         data['CUSTOMER_SEGMENTS'],
                         height=300,
                         use_container_width=True
                     )
                     st.subheader("Top States")
                     st.dataframe(
                         data['GEOGRAPHIC_DISTRIBUTION'].head(),
                         height=300,
                         use_container_width=True
                     )
                     
             with right_col:
                 with st.expander("Product Analysis", expanded=True):
                     st.subheader("Top Products")
                     st.dataframe(
                         data['TOP_PRODUCTS'],
                         height=300,
                         use_container_width=True
                     )
                 
                 with st.expander("Trend Analysis", expanded=True):
                     st.subheader("Sales Trend")
                     st.dataframe(
                         data['SALES_TREND'],
                         height=300,
                         use_container_width=True
                     )
                     st.subheader("Customer Growth")
                     st.dataframe(
                         data['CUSTOMER_GROWTH'],
                         height=300,
                         use_container_width=True
                     )

         # AI Analysis section
         if generate_button:
             st.divider()
             with st.spinner("Generating analysis..."):
                 analysis = generate_analysis(data, selected_prompt)
                 st.markdown(analysis)

  with tab2:
       st.header("Ask Questions About Your Data")
       
       # Check if Snowflake is available
       snowflake_available = is_snowflake_available()
       
       # Database selection
       db_options = ["SQLite"]
       if snowflake_available:
           db_options.append("Snowflake")
       
       db_type = st.selectbox(
           "Select Database",
           db_options,
           key="db_selector"
       ).lower()
       
       if not snowflake_available and len(db_options) == 1:
           st.info("Snowflake support is not available. Only SQLite queries are supported.")
       
       # Validate Snowflake environment variables if Snowflake is selected
       if db_type == "snowflake":
           is_valid, missing_vars = validate_snowflake_env()
           if not is_valid:
               st.error(f"Missing required Snowflake environment variables: {', '.join(missing_vars)}")
               st.info("Please set these environment variables in your Streamlit Cloud deployment settings.")
               st.stop()
       
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
       
       with st.form(key="query_form"):
           col1, col2 = st.columns([6, 1])
           with col1:
               user_question = st.text_input("Ask a question about your data:")
           with col2:
               st.write("")  # Spacer
               clear = st.form_submit_button("Clear")
           submit = st.form_submit_button("Submit")

           if clear:
               user_question = ""
           
       if submit and user_question:
           with st.spinner("Generating and executing query..."):
               try:
                   sql_query = generate_dynamic_query(user_question, db_type=db_type)
                   st.code(sql_query, language="sql")  # Always show the query
                   
                   results = execute_dynamic_query(sql_query, user_question, db_type=db_type)
                   if isinstance(results, pd.DataFrame):
                       st.dataframe(results)
                   else:
                       st.error(results)
                       # Show detailed error for debugging
                       st.error("Full error details:")
                       st.code(traceback.format_exc())
               except Exception as e:
                   st.error(f"Error: {str(e)}")
                   st.error("Full error details:")
                   st.code(traceback.format_exc())

if __name__ == "__main__":
   main()
