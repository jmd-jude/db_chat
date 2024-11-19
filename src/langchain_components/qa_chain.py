from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import sqlite3
import pandas as pd

def get_table_schema():
    conn = sqlite3.connect('sample.db')
    cursor = conn.execute("""
        SELECT sql 
        FROM sqlite_master 
        WHERE type='table' 
        AND name IN ('customers', 'orders')
    """)
    schema = [row[0] for row in cursor.fetchall()]
    
    return "\n".join(schema)

def create_sql_generation_prompt():
    table_schema = get_table_schema()
    
    template = """You are an expert SQL query generator for an e-commerce database.
    Given the table schema and a natural language question, generate a SQL query to answer the question.

    Table Schema:
    {schema}

    Key Business Context:
    - Customers table contains customer demographics and registration data
    - Orders table contains transaction details including products, prices, and delivery info
    - Product categories are 'Electronics', 'Office Supplies', and 'Accessories'
    - Payment methods include 'Credit Card', 'PayPal', and 'Bank Transfer'
    - Dates are in standard YYYY-MM-DD format
    - Total_price is the final order amount including quantity * price

    Sample valid queries:
    -- Sales by category with average order value
    SELECT 
        category,
        COUNT(*) as order_count,
        ROUND(SUM(total_price), 2) as revenue,
        ROUND(AVG(total_price), 2) as avg_order_value
    FROM orders
    GROUP BY category;

    -- Customer purchase frequency
    SELECT 
        c.state,
        COUNT(DISTINCT c.id) as customers,
        COUNT(o.id) as orders,
        ROUND(AVG(o.total_price), 2) as avg_order_value
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id
    GROUP BY c.state;

    Question: {question}

    Return only the SQL query, nothing else.
    Make sure to:
    1. Use only columns that exist in the schema
    2. Include appropriate JOIN conditions when combining tables
    3. Format monetary values using ROUND(..., 2)
    4. Only add LIMIT clause if specifically requested or for non-aggregated results

    SQL Query:"""
    
    return ChatPromptTemplate.from_template(template)

def generate_dynamic_query(question: str):
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    prompt = create_sql_generation_prompt()
    
    messages = prompt.format_messages(
        schema=get_table_schema(),
        question=question
    )
    
    response = llm.invoke(messages)
    # Clean the response of code block markers
    sql = response.content.strip('`').replace('sql', '').strip()
    return sql

def execute_dynamic_query(query: str):
    conn = sqlite3.connect('sample.db')
    try:
        result = pd.read_sql_query(query, conn)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}"