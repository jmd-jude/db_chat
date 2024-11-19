#src/database/queries.py
import pandas as pd

class StandardMetricQueries:
    SALES_OVERVIEW = """
    SELECT 
        strftime('%Y-%m', order_date) as month,
        COUNT(DISTINCT customer_id) as unique_customers,
        COUNT(*) as total_orders,
        ROUND(SUM(total_price), 2) as total_revenue,
        ROUND(AVG(total_price), 2) as avg_order_value
    FROM orders
    GROUP BY month
    ORDER BY month DESC
    LIMIT 12
    """

    CATEGORY_PERFORMANCE = """
    SELECT 
        category,
        COUNT(*) as order_count,
        COUNT(DISTINCT customer_id) as customer_count,
        ROUND(SUM(total_price), 2) as revenue,
        ROUND(AVG(total_price), 2) as avg_order_value
    FROM orders
    GROUP BY category
    ORDER BY revenue DESC
    """

    CUSTOMER_METRICS = """
    SELECT 
        COUNT(DISTINCT c.id) as total_customers,
        ROUND(AVG(orders_per_customer), 2) as avg_orders_per_customer,
        ROUND(AVG(customer_total_spend), 2) as avg_customer_lifetime_value
    FROM customers c
    LEFT JOIN (
        SELECT 
            customer_id,
            COUNT(*) as orders_per_customer,
            SUM(total_price) as customer_total_spend
        FROM orders
        GROUP BY customer_id
    ) o ON c.id = o.customer_id
    """

    PAYMENT_METHODS = """
    SELECT 
        payment_method,
        COUNT(*) as usage_count,
        ROUND(SUM(total_price), 2) as total_processed,
        ROUND(AVG(total_price), 2) as avg_transaction
    FROM orders
    GROUP BY payment_method
    ORDER BY usage_count DESC
    """

    TOP_PRODUCTS = """
    SELECT 
        product_name,
        COUNT(*) as times_ordered,
        SUM(quantity) as units_sold,
        ROUND(SUM(total_price), 2) as revenue
    FROM orders
    GROUP BY product_name
    ORDER BY revenue DESC
    LIMIT 10
    """

    GEOGRAPHIC_DISTRIBUTION = """
   SELECT 
       c.state,
       COUNT(DISTINCT c.id) as customer_count,
       COUNT(o.id) as order_count,
       ROUND(SUM(o.total_price), 2) as revenue,
       ROUND(AVG(o.total_price), 2) as avg_order_value
   FROM customers c
   LEFT JOIN orders o ON c.id = o.customer_id
   GROUP BY c.state
   ORDER BY revenue DESC
   """

    SALES_TREND = """
   SELECT 
       strftime('%Y-%m', order_date) as month,
       COUNT(*) as orders,
       COUNT(DISTINCT customer_id) as unique_customers,
       ROUND(SUM(total_price), 2) as revenue,
       ROUND(AVG(total_price), 2) as avg_order_value
   FROM orders
   GROUP BY month
   ORDER BY month
   """

    CATEGORY_TREND = """
   SELECT 
       strftime('%Y-%m', order_date) as month,
       category,
       COUNT(*) as orders,
       ROUND(SUM(total_price), 2) as revenue,
       ROUND(AVG(total_price), 2) as avg_order_value
   FROM orders
   GROUP BY month, category
   ORDER BY month, revenue DESC
   """

    CUSTOMER_GROWTH = """
   SELECT 
       strftime('%Y-%m', created_at) as month,
       COUNT(*) as new_customers,
       COUNT(*) OVER (ORDER BY created_at) as cumulative_customers
   FROM customers
   GROUP BY month
   ORDER BY month
   """

    CUSTOMER_RETENTION = """
    WITH monthly_active AS (
        SELECT DISTINCT
            strftime('%Y-%m', order_date) as month,
            customer_id,
            FIRST_VALUE(strftime('%Y-%m', order_date)) OVER (
                PARTITION BY customer_id ORDER BY order_date
            ) as first_purchase_month
        FROM orders
    )
    SELECT 
        month,
        COUNT(DISTINCT CASE WHEN month = first_purchase_month THEN customer_id END) as new_customers,
        COUNT(DISTINCT CASE WHEN month != first_purchase_month THEN customer_id END) as returning_customers,
        COUNT(DISTINCT customer_id) as total_customers
    FROM monthly_active
    GROUP BY month
    ORDER BY month
    """

    PAYMENT_METHOD_TREND = """
    SELECT 
        strftime('%Y-%m', order_date) as month,
        payment_method,
        COUNT(*) as transactions,
        ROUND(SUM(total_price), 2) as volume
    FROM orders
    GROUP BY month, payment_method
    ORDER BY month, volume DESC
    """

    PRODUCT_PERFORMANCE_TREND = """
    SELECT 
        strftime('%Y-%m', order_date) as month,
        product_name,
        COUNT(*) as order_count,
        SUM(quantity) as units_sold,
        ROUND(AVG(price), 2) as avg_unit_price,
        ROUND(SUM(total_price), 2) as revenue
    FROM orders
    GROUP BY month, product_name
    ORDER BY month, revenue DESC
    """

    DELIVERY_PERFORMANCE = """
    SELECT 
        strftime('%Y-%m', order_date) as month,
        AVG(julianday(delivery_date) - julianday(order_date)) as avg_delivery_days,
        COUNT(*) as total_orders,
        COUNT(CASE WHEN julianday(delivery_date) - julianday(order_date) <= 7 THEN 1 END) as within_week
    FROM orders
    GROUP BY month
    ORDER BY month
    """

    CUSTOMER_SEGMENTS = """
    WITH customer_stats AS (
        SELECT 
            customer_id,
            COUNT(*) as order_count,
            ROUND(SUM(total_price), 2) as total_spent,
            ROUND(AVG(total_price), 2) as avg_order_value,
            MAX(order_date) as last_order,
            MIN(order_date) as first_order
        FROM orders
        GROUP BY customer_id
    )
    SELECT 
        CASE 
            WHEN order_count >= 10 AND total_spent >= 5000 THEN 'VIP'
            WHEN order_count >= 5 THEN 'Regular'
            WHEN order_count >= 2 THEN 'Occasional'
            ELSE 'One-time'
        END as customer_segment,
        COUNT(*) as customer_count,
        ROUND(AVG(total_spent), 2) as avg_customer_value,
        ROUND(AVG(order_count), 1) as avg_orders
    FROM customer_stats
    GROUP BY customer_segment
    ORDER BY avg_customer_value DESC
    """

    def execute_query(self, conn, query_name):
        query = getattr(self, query_name)
        return pd.read_sql_query(query, conn)

def test_queries():
    import sqlite3
    
    # Connect to database 
    conn = sqlite3.connect('sample.db')
    
    # Initialize queries
    queries = StandardMetricQueries()
    
    # Test each metric
    for query_name in [attr for attr in dir(StandardMetricQueries) if not attr.startswith('_') and attr != 'execute_query']:
        print(f"\n{query_name}:")
        result = queries.execute_query(conn, query_name)
        print(result)
        print("-" * 80)

if __name__ == "__main__":
    test_queries()