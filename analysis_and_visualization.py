import os
import sys
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Force UTF-8 on Windows stdout
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup paths
base_dir = r"E:\Abdul Latif\Abdul Latif Profile\Data Analytics\Anti Gravity\food_hunter"
db_path = os.path.join(base_dir, "foodhunter.db")
charts_dir = os.path.join(base_dir, "charts")
os.makedirs(charts_dir, exist_ok=True)

# Connect to database
conn = sqlite3.connect(db_path)

print("="*60)
print("FOODHUNTER DATA ANALYSIS & VISUALIZATION")
print("="*60)

# 1. Overall Metrics
orders_summary = pd.read_sql_query("""
    SELECT 
        COUNT(*) AS total_orders,
        ROUND(SUM(final_price), 2) AS total_revenue,
        ROUND(AVG(final_price), 2) AS avg_order_value,
        ROUND(SUM(total_price), 2) AS food_total,
        ROUND(SUM(delivery_fee), 2) AS total_delivery_fees,
        ROUND(SUM(discount), 2) AS total_discounts
    FROM orders;
""", conn)
print("\n--- KPI Summary ---")
print(orders_summary.to_string(index=False))

# 2. Monthly Trends
monthly_df = pd.read_sql_query("""
    SELECT 
        strftime('%Y-%m', order_date) AS month,
        COUNT(*) AS orders,
        ROUND(SUM(final_price), 2) AS revenue,
        ROUND(AVG(final_price), 2) AS avg_order
    FROM orders
    GROUP BY strftime('%Y-%m', order_date)
    ORDER BY month;
""", conn)
print("\n--- Monthly Revenue & Orders ---")
print(monthly_df.to_string(index=False))

# 3. Cuisine Performance
cuisine_df = pd.read_sql_query("""
    SELECT 
        r.cuisine,
        COUNT(DISTINCT o.order_id) AS orders,
        ROUND(SUM(o.final_price), 2) AS revenue,
        ROUND(AVG(o.final_price), 2) AS avg_order
    FROM (
        SELECT oi.order_id, MIN(f.restaurant_id) AS restaurant_id
        FROM orders_items oi
        JOIN food_items f ON f.item_id = oi.item_id
        GROUP BY oi.order_id
    ) x
    JOIN orders o ON o.order_id = x.order_id
    JOIN restaurants r ON r.restaurant_id = x.restaurant_id
    GROUP BY r.cuisine
    ORDER BY revenue DESC;
""", conn)
print("\n--- Revenue by Cuisine ---")
print(cuisine_df.to_string(index=False))

# 4. Top Dishes
dishes_df = pd.read_sql_query("""
    SELECT 
        f.item_name,
        SUM(oi.quantity) AS total_qty_sold,
        COUNT(DISTINCT oi.order_id) AS total_orders
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    GROUP BY f.item_name
    ORDER BY total_qty_sold DESC
    LIMIT 10;
""", conn)
print("\n--- Top 10 Dishes Sold ---")
print(dishes_df.to_string(index=False))

# 5. Delivery Times
# Calculate delivery minutes: (delivered_time - order_time) in minutes
delivery_df = pd.read_sql_query("""
    SELECT 
        order_id,
        order_date,
        order_time,
        delivered_time,
        (strftime('%H', delivered_time)*60 + strftime('%M', delivered_time)) - 
        (strftime('%H', order_time)*60 + strftime('%M', order_time)) AS delivery_minutes
    FROM orders
    WHERE delivered_time IS NOT NULL AND order_time IS NOT NULL;
""", conn)
# Clean negative minutes if any crossed midnight
delivery_df['delivery_minutes'] = delivery_df['delivery_minutes'].apply(lambda x: x + 1440 if x < 0 else x)

# 6. Weekday vs Weekend
day_type_df = pd.read_sql_query("""
    SELECT 
        CASE WHEN strftime('%w', order_date) IN ('0', '6') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        COUNT(*) AS orders,
        ROUND(SUM(final_price), 2) AS revenue,
        ROUND(AVG(final_price), 2) AS avg_order
    FROM orders
    GROUP BY day_type;
""", conn)
print("\n--- Weekday vs Weekend ---")
print(day_type_df.to_string(index=False))

conn.close()

# -------------------------------------------------------------
# PLOTTING WITH MATPLOTLIB & SEABORN
# -------------------------------------------------------------
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

# Chart 1: Monthly Trends (Revenue & Orders)
fig, ax1 = plt.subplots(figsize=(10, 5))
color = '#1f77b4'
ax1.set_xlabel('Month', fontweight='bold')
ax1.set_ylabel('Total Revenue ($)', color=color, fontweight='bold')
bars = ax1.bar(monthly_df['month'], monthly_df['revenue'], color=color, alpha=0.7, width=0.4, label='Revenue ($)')
ax1.tick_params(axis='y', labelcolor=color)

# Second y-axis for orders
ax2 = ax1.twinx()
color = '#ff7f0e'
ax2.set_ylabel('Order Count', color=color, fontweight='bold')
lines = ax2.plot(monthly_df['month'], monthly_df['orders'], color=color, marker='o', linewidth=2.5, label='Orders')
ax2.tick_params(axis='y', labelcolor=color)
ax2.grid(False)

plt.title('FoodHunter: Monthly Revenue & Order Volume (2022)', fontsize=14, fontweight='bold', pad=15)
fig.tight_layout()
monthly_chart_path = os.path.join(charts_dir, "monthly_trends.png")
plt.savefig(monthly_chart_path, dpi=300)
plt.close()
print(f"Saved: {monthly_chart_path}")

# Chart 2: Revenue by Cuisine
fig, ax = plt.subplots(figsize=(9, 5))
palette = sns.color_palette("viridis", len(cuisine_df))
sns.barplot(data=cuisine_df, x='cuisine', y='revenue', palette=palette, ax=ax)
for p in ax.patches:
    ax.annotate(f"${p.get_height():,.0f}", (p.get_x() + p.get_width() / 2., p.get_height()),
                ha='center', va='center', xytext=(0, 7), textcoords='offset points', fontweight='bold', fontsize=10)
plt.title('Total Revenue by Cuisine', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Cuisine', fontweight='bold')
plt.ylabel('Revenue ($)', fontweight='bold')
plt.tight_layout()
cuisine_chart_path = os.path.join(charts_dir, "revenue_by_cuisine.png")
plt.savefig(cuisine_chart_path, dpi=300)
plt.close()
print(f"Saved: {cuisine_chart_path}")

# Chart 3: Top 10 Dishes Sold
fig, ax = plt.subplots(figsize=(10, 6))
sns.barplot(data=dishes_df, x='total_qty_sold', y='item_name', palette="crest", ax=ax)
for p in ax.patches:
    ax.annotate(f"{int(p.get_width()):,}", (p.get_width(), p.get_y() + p.get_height() / 2.),
                ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontweight='bold', fontsize=10)
plt.title('Top 10 Most Ordered Food Items', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Total Quantity Sold', fontweight='bold')
plt.ylabel('Dish Name', fontweight='bold')
plt.xlim(0, dishes_df['total_qty_sold'].max() * 1.15)
plt.tight_layout()
dishes_chart_path = os.path.join(charts_dir, "top_10_dishes.png")
plt.savefig(dishes_chart_path, dpi=300)
plt.close()
print(f"Saved: {dishes_chart_path}")

# Chart 4: Delivery Time Distribution
fig, ax = plt.subplots(figsize=(9, 5))
sns.histplot(delivery_df['delivery_minutes'], bins=30, kde=True, color='#2ca02c', ax=ax)
avg_time = delivery_df['delivery_minutes'].mean()
ax.axvline(avg_time, color='red', linestyle='--', linewidth=2, label=f'Avg: {avg_time:.1f} mins')
plt.title('Distribution of Delivery Times (Minutes)', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Delivery Time (minutes)', fontweight='bold')
plt.ylabel('Number of Orders', fontweight='bold')
plt.legend()
plt.tight_layout()
delivery_chart_path = os.path.join(charts_dir, "delivery_distribution.png")
plt.savefig(delivery_chart_path, dpi=300)
plt.close()
print(f"Saved: {delivery_chart_path}")

# -------------------------------------------------------------
# INTERACTIVE PLOTLY HTML DASHBOARD
# -------------------------------------------------------------
fig_interactive = make_subplots(
    rows=2, cols=2,
    subplot_titles=(
        "Monthly Orders & Revenue",
        "Revenue by Cuisine ($)",
        "Top 10 Most Ordered Dishes",
        "Delivery Time Distribution (KDE/Hist)"
    ),
    specs=[[{"secondary_y": True}, {"type": "bar"}],
           [{"type": "bar"}, {"type": "histogram"}]]
)

# 1. Monthly trend
fig_interactive.add_trace(
    go.Bar(x=monthly_df['month'], y=monthly_df['revenue'], name="Revenue ($)", marker_color="#3366cc"),
    row=1, col=1, secondary_y=False
)
fig_interactive.add_trace(
    go.Scatter(x=monthly_df['month'], y=monthly_df['orders'], name="Orders", mode="lines+markers", marker_color="#ff9900"),
    row=1, col=1, secondary_y=True
)

# 2. Cuisine
fig_interactive.add_trace(
    go.Bar(x=cuisine_df['cuisine'], y=cuisine_df['revenue'], name="Cuisine Rev", marker_color="#109618", text=cuisine_df['revenue'], textposition='outside'),
    row=1, col=2
)

# 3. Top Dishes
fig_interactive.add_trace(
    go.Bar(x=dishes_df['total_qty_sold'], y=dishes_df['item_name'], orientation='h', name="Dishes", marker_color="#990099"),
    row=2, col=1
)

# 4. Delivery
fig_interactive.add_trace(
    go.Histogram(x=delivery_df['delivery_minutes'], nbinsx=30, name="Delivery Time", marker_color="#0099c6"),
    row=2, col=2
)

fig_interactive.update_layout(
    title_text="🍽️ FoodHunter Comprehensive Analytics Dashboard",
    height=800,
    showlegend=False,
    template="plotly_white"
)

html_dashboard_path = os.path.join(base_dir, "foodhunter_dashboard.html")
fig_interactive.write_html(html_dashboard_path)
print(f"Saved Interactive HTML Dashboard: {html_dashboard_path}")
print("\n[SUCCESS] All analysis and visualizations completed successfully!")
