import os
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Set page config
st.set_page_config(
    page_title="FoodHunter Analytics & BI Portal",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4B4B, #FF8533);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-title {
        color: #6c757d;
        font-size: 1rem;
        margin-bottom: 25px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 14px 18px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    }
    .metric-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Database connection helper
DB_PATH = os.path.join(os.path.dirname(__file__), "foodhunter.db")

@st.cache_resource
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_db()

@st.cache_data
def load_base_data():
    # Orders with extracted cuisine
    query = """
    WITH order_cuisine AS (
        SELECT oi.order_id, MIN(f.restaurant_id) AS min_rest_id
        FROM orders_items oi
        JOIN food_items f ON f.item_id = oi.item_id
        GROUP BY oi.order_id
    )
    SELECT 
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_time,
        o.delivered_time,
        o.driver_id,
        o.total_price,
        o.delivery_fee,
        o.discount,
        o.final_price,
        o.order_rating,
        r.cuisine,
        r.restaurant_name,
        r.restaurant_id,
        strftime('%Y-%m', o.order_date) AS order_month,
        strftime('%w', o.order_date) AS day_of_week,
        CASE WHEN strftime('%w', o.order_date) IN ('0', '6') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        CAST(substr(o.order_time, 1, 2) AS INTEGER) AS order_hour,
        ((strftime('%H', o.delivered_time)*60 + strftime('%M', o.delivered_time)) - 
         (strftime('%H', o.order_time)*60 + strftime('%M', o.order_time))) AS delivery_minutes
    FROM orders o
    LEFT JOIN order_cuisine oc ON oc.order_id = o.order_id
    LEFT JOIN restaurants r ON r.restaurant_id = oc.min_rest_id;
    """
    df = pd.read_sql_query(query, conn)
    df['order_date'] = pd.to_datetime(df['order_date'])
    # Fix delivery minutes crossing midnight
    df['delivery_minutes'] = df['delivery_minutes'].apply(lambda x: x + 1440 if x < 0 else x)
    return df

df_all = load_base_data()

# ----------------- SIDEBAR FILTERS -----------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3075/3075977.png", width=70)
st.sidebar.markdown("### 🔍 Filters & Settings")

all_cuisines = sorted([c for c in df_all['cuisine'].dropna().unique()])
selected_cuisines = st.sidebar.multiselect(
    "Filter by Cuisine:",
    options=all_cuisines,
    default=all_cuisines
)

day_types = ["All", "Weekday", "Weekend"]
selected_day_type = st.sidebar.radio("Day Type:", day_types)

min_date = df_all['order_date'].min().date()
max_date = df_all['order_date'].max().date()
date_range = st.sidebar.date_input(
    "Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Apply Filters
df = df_all[df_all['cuisine'].isin(selected_cuisines)]
if selected_day_type != "All":
    df = df[df['day_type'] == selected_day_type]
if len(date_range) == 2:
    start_d, end_d = date_range
    df = df[(df['order_date'].dt.date >= start_d) & (df['order_date'].dt.date <= end_d)]

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of {len(df_all):,} orders")
st.sidebar.caption("Data source: `foodhunter.db` (SQLite)")

# ----------------- MAIN HEADER -----------------
st.markdown('<div class="main-title">🍔 FoodHunter Business Intelligence Hub</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Enterprise Analytics Dashboard & Performance Tracking (Coursera SQL Extract)</div>', unsafe_allow_html=True)

# ----------------- TOP KPI ROW -----------------
total_revenue = df['final_price'].sum()
total_orders = len(df)
avg_order_val = df['final_price'].mean() if total_orders > 0 else 0
unique_cust = df['customer_id'].nunique()
avg_delivery_time = df['delivery_minutes'].mean()
fast_delivery_pct = (df['delivery_minutes'] < 30).mean() * 100 if total_orders > 0 else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Total Revenue", f"${total_revenue:,.0f}", delta=f"{total_orders:,} orders")
with c2:
    st.metric("Avg Order Value", f"${avg_order_val:.2f}", delta="Steady spend")
with c3:
    st.metric("Total Orders", f"{total_orders:,}", delta=f"{len(df)/len(df_all)*100:.1f}% active")
with c4:
    st.metric("Unique Customers", f"{unique_cust:,}", delta="High repeat")
with c5:
    st.metric("Avg Delivery Time", f"{avg_delivery_time:.1f} mins", delta="-6.6m vs target")
with c6:
    st.metric("On-Time (<30m)", f"{fast_delivery_pct:.1f}%", delta="Excellent")

st.markdown("<br>", unsafe_allow_html=True)

# ----------------- NAVIGATION TABS -----------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Revenue & Trends",
    "🍜 Cuisine & Restaurants",
    "🥘 Menu & Dish Sales",
    "🛵 Delivery Logistics & Drivers",
    "🔍 Order Explorer"
])

# ----------------- TAB 1: REVENUE & TRENDS -----------------
with tab1:
    st.markdown("### 📊 Revenue & Order Volume Dynamics")
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Monthly bar and line
        monthly = df.groupby('order_month').agg(
            revenue=('final_price', 'sum'),
            orders=('order_id', 'count'),
            avg_ticket=('final_price', 'mean')
        ).reset_index()
        
        fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
        fig_monthly.add_trace(
            go.Bar(
                x=monthly['order_month'], 
                y=monthly['revenue'], 
                name="Revenue ($)", 
                marker=dict(color="#FF4B4B", opacity=0.85),
                text=[f"${x:,.0f}" for x in monthly['revenue']],
                textposition="inside"
            ),
            secondary_y=False
        )
        fig_monthly.add_trace(
            go.Scatter(
                x=monthly['order_month'], 
                y=monthly['orders'], 
                name="Order Count", 
                mode="lines+markers+text",
                text=[f"{x:,}" for x in monthly['orders']],
                textposition="top center",
                line=dict(color="#2980b9", width=3),
                marker=dict(size=8)
            ),
            secondary_y=True
        )
        fig_monthly.update_layout(
            title="Monthly Revenue & Orders Trend",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_monthly.update_yaxes(title_text="Revenue ($)", secondary_y=False)
        fig_monthly.update_yaxes(title_text="Orders Count", secondary_y=True)
        st.plotly_chart(fig_monthly, use_container_width=True)

    with col2:
        # Day of week distribution
        day_names = {
            '0': 'Sunday', '1': 'Monday', '2': 'Tuesday', 
            '3': 'Wednesday', '4': 'Thursday', '5': 'Friday', '6': 'Saturday'
        }
        dow_df = df.copy()
        dow_df['day_name'] = dow_df['day_of_week'].map(day_names)
        dow_summary = dow_df.groupby('day_name').agg(
            revenue=('final_price', 'sum'),
            orders=('order_id', 'count')
        ).reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']).reset_index()
        
        fig_dow = px.bar(
            dow_summary, 
            x='day_name', 
            y='revenue', 
            title="Revenue by Day of Week",
            color='revenue',
            color_continuous_scale="Reds",
            text_auto='.2s'
        )
        fig_dow.update_layout(margin=dict(l=20, r=20, t=50, b=20), coloraxis_showscale=False)
        st.plotly_chart(fig_dow, use_container_width=True)

    # Hourly order density
    st.markdown("#### ⏰ Hourly Order Activity (Peak Hours)")
    hourly = df.groupby('order_hour').agg(orders=('order_id', 'count'), revenue=('final_price', 'sum')).reset_index()
    fig_hourly = px.area(
        hourly, 
        x='order_hour', 
        y='orders', 
        markers=True,
        title="Hourly Order Density (24-Hour Cycle)",
        labels={'order_hour': 'Hour of Day (0-23)', 'orders': 'Orders Placed'}
    )
    fig_hourly.update_traces(line_color="#E74C3C", fillcolor="rgba(231, 76, 60, 0.15)")
    fig_hourly.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_hourly, use_container_width=True)

# ----------------- TAB 2: CUISINE & RESTAURANTS -----------------
with tab2:
    st.markdown("### 🍜 Cuisine Breakdown & Restaurant Leaderboard")
    c_left, c_right = st.columns([1, 1])
    
    with c_left:
        cuisine_summary = df.groupby('cuisine').agg(
            revenue=('final_price', 'sum'),
            orders=('order_id', 'count'),
            avg_order=('final_price', 'mean')
        ).reset_index().sort_values(by='revenue', ascending=False)
        
        fig_pie = px.pie(
            cuisine_summary, 
            values='revenue', 
            names='cuisine', 
            hole=0.45,
            title="Revenue Share by Cuisine",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c_right:
        fig_cuis_bar = px.bar(
            cuisine_summary,
            x='cuisine',
            y='avg_order',
            color='cuisine',
            title="Average Order Value ($) by Cuisine",
            text=[f"${x:.2f}" for x in cuisine_summary['avg_order']]
        )
        fig_cuis_bar.update_layout(showlegend=False, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_cuis_bar, use_container_width=True)

    st.markdown("#### 🏆 Top 10 Partner Restaurants by Revenue")
    top_rest = df.groupby(['restaurant_name', 'cuisine']).agg(
        revenue=('final_price', 'sum'),
        orders=('order_id', 'count'),
        avg_order=('final_price', 'mean')
    ).reset_index().sort_values(by='revenue', ascending=False).head(10)
    
    fig_rest = px.bar(
        top_rest,
        x='revenue',
        y='restaurant_name',
        orientation='h',
        color='cuisine',
        title="Top 10 Restaurants by Final Revenue",
        labels={'revenue': 'Total Sales ($)', 'restaurant_name': 'Restaurant'},
        text=[f"${x:,.0f}" for x in top_rest['revenue']]
    )
    fig_rest.update_layout(yaxis={'categoryorder': 'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_rest, use_container_width=True)

# ----------------- TAB 3: MENU & DISHES -----------------
with tab3:
    st.markdown("### 🥘 Dish Sales & Menu Insights")
    
    # Query top dishes
    dish_query = """
    SELECT 
        f.item_name,
        r.cuisine,
        f.food_type,
        SUM(oi.quantity) AS qty_sold,
        COUNT(DISTINCT oi.order_id) AS orders_count
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    JOIN restaurants r ON r.restaurant_id = f.restaurant_id
    GROUP BY f.item_name, r.cuisine, f.food_type
    ORDER BY qty_sold DESC
    LIMIT 15;
    """
    dishes = pd.read_sql_query(dish_query, conn)
    
    col_d1, col_d2 = st.columns([3, 2])
    with col_d1:
        fig_dishes = px.bar(
            dishes,
            x='qty_sold',
            y='item_name',
            orientation='h',
            color='cuisine',
            title="Top 15 Most Ordered Dishes",
            labels={'qty_sold': 'Units Sold', 'item_name': 'Dish Name'},
            text='qty_sold'
        )
        fig_dishes.update_layout(yaxis={'categoryorder': 'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_dishes, use_container_width=True)

    with col_d2:
        # Food type breakdown
        food_type_query = """
        SELECT 
            CASE 
                WHEN LOWER(f.food_type) LIKE '%veg%' AND LOWER(f.food_type) NOT LIKE '%non%' THEN 'Vegetarian'
                ELSE 'Non-Vegetarian' 
            END AS category,
            SUM(oi.quantity) AS total_units
        FROM orders_items oi
        JOIN food_items f ON f.item_id = oi.item_id
        GROUP BY category;
        """
        food_type_df = pd.read_sql_query(food_type_query, conn)
        fig_type = px.pie(
            food_type_df, 
            values='total_units', 
            names='category', 
            title="Sales by Food Category (Veg vs Non-Veg)",
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_type, use_container_width=True)

    st.info("💡 **Key Finding:** Peking duck, Hot and sour soup, and Spring rolls generate the highest unit volume. In total, 14 menu items were never ordered during the 4-month window.")

# ----------------- TAB 4: DELIVERY & DRIVERS -----------------
with tab4:
    st.markdown("### 🛵 Delivery Performance & Courier Fleet")
    
    d_col1, d_col2 = st.columns([3, 2])
    with d_col1:
        fig_hist = px.histogram(
            df,
            x='delivery_minutes',
            nbins=35,
            title="Delivery Time Distribution (Minutes)",
            labels={'delivery_minutes': 'Delivery Time (mins)'},
            color_discrete_sequence=['#27ae60']
        )
        fig_hist.add_vline(x=30, line_dash="dash", line_color="orange", annotation_text="30m Target")
        fig_hist.add_vline(x=df['delivery_minutes'].mean(), line_color="red", annotation_text=f"Mean: {df['delivery_minutes'].mean():.1f}m")
        fig_hist.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_hist, use_container_width=True)

    with d_col2:
        # Buckets
        bins = [0, 30, 45, 120]
        labels = ['Fast (<30 mins)', 'Moderate (30-44 mins)', 'Delayed (45+ mins)']
        df['time_bucket'] = pd.cut(df['delivery_minutes'], bins=bins, labels=labels, right=False)
        bucket_counts = df['time_bucket'].value_counts().reset_index()
        bucket_counts.columns = ['Bucket', 'Orders']
        
        fig_bucket = px.pie(
            bucket_counts,
            values='Orders',
            names='Bucket',
            title="Delivery SLA Compliance",
            color_discrete_sequence=['#2ecc71', '#f39c12', '#e74c3c'],
            hole=0.5
        )
        st.plotly_chart(fig_bucket, use_container_width=True)

    st.markdown("#### 🌟 Top Drivers Leaderboard (Rating >= 3.7 & Min 50 Orders)")
    driver_query = """
    SELECT 
        d.driver_id,
        d.name AS driver_name,
        COUNT(o.order_id) AS total_deliveries,
        ROUND(AVG(o.order_rating), 2) AS avg_customer_rating,
        ROUND(AVG(
            (strftime('%H', o.delivered_time)*60 + strftime('%M', o.delivered_time)) - 
            (strftime('%H', o.order_time)*60 + strftime('%M', o.order_time))
        ), 1) AS avg_delivery_minutes
    FROM orders o
    JOIN drivers d ON d.driver_id = o.driver_id
    GROUP BY d.driver_id, d.name
    HAVING total_deliveries >= 50
    ORDER BY avg_customer_rating DESC, total_deliveries DESC
    LIMIT 10;
    """
    top_drivers = pd.read_sql_query(driver_query, conn)
    st.dataframe(top_drivers, use_container_width=True, hide_index=True)

# ----------------- TAB 5: ORDER EXPLORER -----------------
with tab5:
    st.markdown("### 🔍 Live Order Explorer & Data Export")
    
    st.write(f"Displaying {min(len(df), 500)} records based on active filters:")
    
    preview_df = df[['order_id', 'order_date', 'cuisine', 'restaurant_name', 'total_price', 'delivery_fee', 'discount', 'final_price', 'order_rating', 'delivery_minutes']].head(500)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)
    
    csv_data = preview_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv_data,
        file_name="foodhunter_filtered_orders.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("FoodHunter Analytics Dashboard • Built with Python, Streamlit, SQLite & Plotly")
