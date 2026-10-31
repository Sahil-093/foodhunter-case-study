import os
import sys
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Force UTF-8 on Windows stdout
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"E:\Abdul Latif\Abdul Latif Profile\Data Analytics\Anti Gravity\food_hunter"
db_path = os.path.join(base_dir, "foodhunter.db")
output_html = os.path.join(base_dir, "index.html")

conn = sqlite3.connect(db_path)

# 1. Monthly data
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

# 2. Cuisine data
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

# 3. Top Dishes
dishes_df = pd.read_sql_query("""
    SELECT 
        f.item_name,
        r.cuisine,
        SUM(oi.quantity) AS total_qty_sold,
        COUNT(DISTINCT oi.order_id) AS total_orders
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    JOIN restaurants r ON r.restaurant_id = f.restaurant_id
    GROUP BY f.item_name, r.cuisine
    ORDER BY total_qty_sold DESC
    LIMIT 12;
""", conn)

# 4. Delivery data
delivery_df = pd.read_sql_query("""
    SELECT 
        ((strftime('%H', delivered_time)*60 + strftime('%M', delivered_time)) - 
         (strftime('%H', order_time)*60 + strftime('%M', order_time))) AS delivery_minutes
    FROM orders
    WHERE delivered_time IS NOT NULL AND order_time IS NOT NULL;
""", conn)
delivery_df['delivery_minutes'] = delivery_df['delivery_minutes'].apply(lambda x: x + 1440 if x < 0 else x)

# 5. Top Drivers
drivers_df = pd.read_sql_query("""
    SELECT 
        d.name,
        COUNT(o.order_id) AS orders_count,
        ROUND(AVG(o.order_rating), 2) AS avg_rating
    FROM orders o
    JOIN drivers d ON d.driver_id = o.driver_id
    GROUP BY d.driver_id, d.name
    HAVING orders_count >= 50
    ORDER BY avg_rating DESC
    LIMIT 8;
""", conn)

# 6. Hourly breakdown
hourly_df = pd.read_sql_query("""
    SELECT 
        CAST(substr(order_time, 1, 2) AS INTEGER) AS hour,
        COUNT(*) AS orders,
        ROUND(SUM(final_price), 2) AS revenue
    FROM orders
    GROUP BY hour
    ORDER BY hour;
""", conn)

conn.close()

# --- CREATE PLOTLY CHARTS ---
# Chart 1: Monthly Dual Axis
fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
fig_monthly.add_trace(
    go.Bar(
        x=monthly_df['month'], y=monthly_df['revenue'],
        name="Revenue ($)",
        marker_color="#4F46E5",
        text=[f"${x:,.0f}" for x in monthly_df['revenue']],
        textposition="inside"
    ),
    secondary_y=False
)
fig_monthly.add_trace(
    go.Scatter(
        x=monthly_df['month'], y=monthly_df['orders'],
        name="Orders Count",
        mode="lines+markers+text",
        text=[f"{x:,}" for x in monthly_df['orders']],
        textposition="top center",
        line=dict(color="#F59E0B", width=3),
        marker=dict(size=8)
    ),
    secondary_y=True
)
fig_monthly.update_layout(
    margin=dict(l=20, r=20, t=30, b=20),
    template="plotly_white",
    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
)
fig_monthly_html = fig_monthly.to_html(full_html=False, include_plotlyjs=False)

# Chart 2: Cuisine Donut
fig_cuisine = px.pie(
    cuisine_df, values='revenue', names='cuisine',
    hole=0.5,
    color_discrete_sequence=['#4F46E5', '#10B981', '#F59E0B', '#EF4444']
)
fig_cuisine.update_traces(textposition='inside', textinfo='percent+label')
fig_cuisine.update_layout(margin=dict(l=20, r=20, t=20, b=20), template="plotly_white")
fig_cuisine_html = fig_cuisine.to_html(full_html=False, include_plotlyjs=False)

# Chart 3: Top Dishes Horizontal Bar
fig_dishes = px.bar(
    dishes_df, x='total_qty_sold', y='item_name', orientation='h',
    color='cuisine',
    color_discrete_sequence=px.colors.qualitative.Safe,
    text='total_qty_sold'
)
fig_dishes.update_layout(
    yaxis={'categoryorder': 'total ascending'},
    margin=dict(l=20, r=20, t=20, b=20),
    template="plotly_white",
    xaxis_title="Units Sold",
    yaxis_title=""
)
fig_dishes_html = fig_dishes.to_html(full_html=False, include_plotlyjs=False)

# Chart 4: Delivery Histogram
fig_delivery = px.histogram(
    delivery_df, x='delivery_minutes', nbins=30,
    color_discrete_sequence=['#10B981']
)
fig_delivery.add_vline(x=30, line_dash="dash", line_color="#EF4444", annotation_text="30m Benchmark")
fig_delivery.update_layout(
    margin=dict(l=20, r=20, t=20, b=20),
    template="plotly_white",
    xaxis_title="Delivery Time (Minutes)",
    yaxis_title="Orders Count"
)
fig_delivery_html = fig_delivery.to_html(full_html=False, include_plotlyjs=False)

# Chart 5: Hourly Peak Curve
fig_hourly = px.area(
    hourly_df, x='hour', y='orders',
    labels={'hour': 'Hour of Day (0-23)', 'orders': 'Order Count'},
    color_discrete_sequence=['#6366F1']
)
fig_hourly.update_layout(margin=dict(l=20, r=20, t=20, b=20), template="plotly_white")
fig_hourly_html = fig_hourly.to_html(full_html=False, include_plotlyjs=False)

# Driver table rows HTML
driver_rows_html = "".join([
    f"""<tr>
        <td><strong>{row['name']}</strong></td>
        <td><span class="badge bg-primary rounded-pill">{row['orders_count']:,} orders</span></td>
        <td><span class="badge bg-warning text-dark"><i class="fas fa-star me-1"></i>{row['avg_rating']}</span></td>
    </tr>"""
    for _, row in drivers_df.iterrows()
])

# Cuisine table rows HTML
cuisine_rows_html = "".join([
    f"""<tr>
        <td><strong>{row['cuisine']}</strong></td>
        <td>{row['orders']:,}</td>
        <td>${row['revenue']:,.2f}</td>
        <td><span class="badge bg-light text-dark border">${row['avg_order']:.2f}</span></td>
    </tr>"""
    for _, row in cuisine_df.iterrows()
])

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FoodHunter Executive Analytics Dashboard</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome 6 -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
    <!-- Google Fonts Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f1f5f9;
            color: #1e293b;
        }}
        .navbar-custom {{
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .kpi-card {{
            background: #ffffff;
            border-radius: 16px;
            padding: 22px;
            border: 1px solid rgba(226, 232, 240, 0.8);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
            transition: all 0.25s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
        }}
        .kpi-icon {{
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }}
        .chart-card {{
            background: #ffffff;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(226, 232, 240, 0.8);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
            margin-bottom: 24px;
        }}
        .badge-subtle {{
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 20px;
        }}
        .section-header {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .pill-tab {{
            border-radius: 30px;
            padding: 8px 18px;
            font-weight: 600;
        }}
    </style>
</head>
<body>

    <!-- NAVBAR -->
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom py-3">
        <div class="container-fluid px-4">
            <a class="navbar-brand d-flex align-items-center gap-2 fw-bold fs-4 text-white" href="#">
                <span class="p-2 bg-danger rounded-3"><i class="fas fa-utensils"></i></span>
                FoodHunter BI Portal
            </a>
            <div class="d-flex align-items-center gap-3">
                <span class="badge bg-success text-white py-2 px-3 rounded-pill">
                    <i class="fas fa-database me-1"></i> 43,118 Orders Loaded
                </span>
                <a href="https://github.com/Sahil-093/foodhunter-case-study" target="_blank" class="btn btn-outline-light btn-sm rounded-pill px-3 fw-semibold shadow-sm">
                    <i class="fab fa-github me-1"></i> View on GitHub
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-4 py-4">

        <!-- SUB HEADER -->
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="fw-extrabold mb-1 text-slate-900">Executive Performance Dashboard</h3>
                <p class="text-muted mb-0">Analysis of FoodHunter SQL Dataset (June 1, 2022 - September 29, 2022)</p>
            </div>
            <div class="text-end">
                <span class="badge bg-light text-dark border px-3 py-2 rounded-pill">
                    <i class="far fa-calendar-alt me-1"></i> Q3 2022 Performance Window
                </span>
            </div>
        </div>

        <!-- KPI SCORECARDS -->
        <div class="row g-3 mb-4">
            <!-- KPI 1: Revenue -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Total Revenue</span>
                        <div class="kpi-icon bg-indigo-50 text-primary" style="background:#EEF2FF; color:#4F46E5;">
                            <i class="fas fa-dollar-sign"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">$1,197,706</h3>
                    <span class="badge-subtle bg-success bg-opacity-10 text-success">
                        <i class="fas fa-arrow-up me-1"></i>43,118 orders
                    </span>
                </div>
            </div>

            <!-- KPI 2: AOV -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Average Order</span>
                        <div class="kpi-icon" style="background:#ECFDF5; color:#10B981;">
                            <i class="fas fa-receipt"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">$27.78</h3>
                    <span class="badge-subtle bg-info bg-opacity-10 text-info">
                        <i class="fas fa-check me-1"></i>Stable spend
                    </span>
                </div>
            </div>

            <!-- KPI 3: Customers -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Repeat Customers</span>
                        <div class="kpi-icon" style="background:#FFFBEB; color:#F59E0B;">
                            <i class="fas fa-user-check"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">94.7%</h3>
                    <span class="badge-subtle bg-warning bg-opacity-10 text-warning">
                        9,349 repeat clients
                    </span>
                </div>
            </div>

            <!-- KPI 4: Top Cuisine -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Top Cuisine</span>
                        <div class="kpi-icon" style="background:#FEF2F2; color:#EF4444;">
                            <i class="fas fa-bowl-rice"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">Chinese</h3>
                    <span class="badge-subtle bg-danger bg-opacity-10 text-danger">
                        $437.7K revenue
                    </span>
                </div>
            </div>

            <!-- KPI 5: Delivery SLA -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Avg Delivery</span>
                        <div class="kpi-icon" style="background:#F0FDF4; color:#22C55E;">
                            <i class="fas fa-motorcycle"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">23.4 min</h3>
                    <span class="badge-subtle bg-success bg-opacity-10 text-success">
                        <i class="fas fa-bolt me-1"></i>82.9% &lt;30m
                    </span>
                </div>
            </div>

            <!-- KPI 6: Active Drivers -->
            <div class="col-md-4 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="text-muted small fw-semibold">Fleet Utilization</span>
                        <div class="kpi-icon" style="background:#F5F3FF; color:#8B5CF6;">
                            <i class="fas fa-users-gear"></i>
                        </div>
                    </div>
                    <h3 class="fw-bold mb-1 text-slate-800">100%</h3>
                    <span class="badge-subtle bg-primary bg-opacity-10 text-primary">
                        250 of 250 active
                    </span>
                </div>
            </div>
        </div>

        <!-- MAIN CHARTS ROW 1 -->
        <div class="row g-4 mb-4">
            <!-- Monthly Trends -->
            <div class="col-xl-8">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-chart-line text-primary"></i>
                        Monthly Revenue & Order Volume Progression
                    </div>
                    <p class="text-muted small mb-3">Order volume dropped by 25.1% from June to September while average ticket price remained locked at ~$27.78.</p>
                    {fig_monthly_html}
                </div>
            </div>

            <!-- Cuisine Revenue Share -->
            <div class="col-xl-4">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-chart-pie text-success"></i>
                        Revenue Share by Cuisine
                    </div>
                    <p class="text-muted small mb-3">Chinese food accounts for over 36.5% of gross sales, followed by Italian (29.8%).</p>
                    {fig_cuisine_html}
                </div>
            </div>
        </div>

        <!-- MAIN CHARTS ROW 2 -->
        <div class="row g-4 mb-4">
            <!-- Top Dishes -->
            <div class="col-xl-7">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-fire-flame-curved text-danger"></i>
                        Top 12 Best-Selling Menu Dishes (Units Sold)
                    </div>
                    {fig_dishes_html}
                </div>
            </div>

            <!-- Delivery Time Distribution -->
            <div class="col-xl-5">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-stopwatch text-warning"></i>
                        Delivery SLA Compliance (Target: &lt;30m)
                    </div>
                    {fig_delivery_html}
                </div>
            </div>
        </div>

        <!-- ROW 3: DETAILED TABLES & HOURLY ACTIVITY -->
        <div class="row g-4 mb-4">
            <!-- Hourly Curve -->
            <div class="col-xl-6">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-clock text-info"></i>
                        Hourly Order Density (24-Hour Cycle)
                    </div>
                    {fig_hourly_html}
                </div>
            </div>

            <!-- Top Drivers Leaderboard -->
            <div class="col-xl-6">
                <div class="chart-card">
                    <div class="section-header">
                        <i class="fas fa-medal text-warning"></i>
                        Top Rated Drivers Fleet (Min 50 Deliveries)
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Driver Name</th>
                                    <th>Orders Completed</th>
                                    <th>Avg Rating</th>
                                </tr>
                            </thead>
                            <tbody>
                                {driver_rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- FOOTER -->
        <footer class="text-center py-4 text-muted small border-top mt-4">
            <p class="mb-1">FoodHunter BI Dashboard &bull; Built with Python, Pandas, SQLite & Plotly</p>
            <p class="mb-0">Powered by Antigravity Data Analytics</p>
        </footer>

    </div>

</body>
</html>
"""

with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[SUCCESS] Modern dashboard built successfully at: {output_html}")
