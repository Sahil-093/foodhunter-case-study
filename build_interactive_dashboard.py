import os
import sys
import json
import sqlite3

# Set encoding
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"E:\Abdul Latif\Abdul Latif Profile\Data Analytics\Anti Gravity\food_hunter"
db_path = os.path.join(base_dir, "foodhunter.db")
output_html = os.path.join(base_dir, "index.html")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Main 32-slice aggregated matrix
matrix_query = """
WITH order_meta AS (
    SELECT 
        o.order_id,
        strftime('%Y-%m', o.order_date) AS month,
        CASE WHEN strftime('%w', o.order_date) IN ('0', '6') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        o.final_price,
        o.total_price,
        o.delivery_fee,
        o.discount,
        ((strftime('%H', o.delivered_time)*60 + strftime('%M', o.delivered_time)) - 
         (strftime('%H', o.order_time)*60 + strftime('%M', o.order_time))) AS deliv_mins,
        r.cuisine
    FROM orders o
    LEFT JOIN (
        SELECT oi.order_id, MIN(f.restaurant_id) AS min_rest
        FROM orders_items oi
        JOIN food_items f ON f.item_id = oi.item_id
        GROUP BY oi.order_id
    ) om ON om.order_id = o.order_id
    LEFT JOIN restaurants r ON r.restaurant_id = om.min_rest
)
SELECT 
    month, 
    cuisine, 
    day_type,
    COUNT(*) AS orders,
    ROUND(SUM(final_price), 2) AS revenue,
    ROUND(SUM(total_price), 2) AS food_total,
    ROUND(SUM(delivery_fee), 2) AS deliv_fee,
    ROUND(SUM(discount), 2) AS discount,
    ROUND(AVG(deliv_mins), 1) AS avg_deliv,
    SUM(CASE WHEN deliv_mins < 30 THEN 1 ELSE 0 END) AS fast_deliv,
    SUM(CASE WHEN deliv_mins BETWEEN 30 AND 44 THEN 1 ELSE 0 END) AS mod_deliv
FROM order_meta
GROUP BY month, cuisine, day_type;
"""
cur.execute(matrix_query)
matrix_data = [
    {
        "month": r[0], "cuisine": r[1], "day_type": r[2],
        "orders": r[3], "revenue": r[4], "food_total": r[5],
        "deliv_fee": r[6], "discount": r[7], "avg_deliv": r[8],
        "fast_deliv": r[9], "mod_deliv": r[10]
    }
    for r in cur.fetchall()
]

# 2. Hourly distribution
hourly_query = """
SELECT 
    CAST(substr(o.order_time, 1, 2) AS INTEGER) AS hour,
    r.cuisine,
    COUNT(*) AS orders,
    ROUND(SUM(o.final_price), 2) AS revenue
FROM orders o
LEFT JOIN (
    SELECT oi.order_id, MIN(f.restaurant_id) AS min_rest
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    GROUP BY oi.order_id
) om ON om.order_id = o.order_id
LEFT JOIN restaurants r ON r.restaurant_id = om.min_rest
GROUP BY hour, r.cuisine
ORDER BY hour;
"""
cur.execute(hourly_query)
hourly_data = [
    {"hour": r[0], "cuisine": r[1], "orders": r[2], "revenue": r[3]}
    for r in cur.fetchall()
]

# 3. Top dishes
dishes_query = """
SELECT 
    f.item_name,
    r.cuisine,
    CASE 
        WHEN LOWER(f.food_type) LIKE '%veg%' AND LOWER(f.food_type) NOT LIKE '%non%' THEN 'Vegetarian'
        ELSE 'Non-Veg' 
    END AS category,
    SUM(oi.quantity) AS qty_sold,
    COUNT(DISTINCT oi.order_id) AS orders_count
FROM orders_items oi
JOIN food_items f ON f.item_id = oi.item_id
JOIN restaurants r ON r.restaurant_id = f.restaurant_id
GROUP BY f.item_name, r.cuisine, category
ORDER BY qty_sold DESC;
"""
cur.execute(dishes_query)
dishes_data = [
    {"name": r[0], "cuisine": r[1], "category": r[2], "qty": r[3], "orders": r[4]}
    for r in cur.fetchall()
]

# 4. Restaurants leaderboard
rest_query = """
SELECT 
    r.restaurant_name,
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
GROUP BY r.restaurant_id, r.restaurant_name, r.cuisine
ORDER BY revenue DESC;
"""
cur.execute(rest_query)
restaurants_data = [
    {"name": r[0], "cuisine": r[1], "orders": r[2], "revenue": r[3], "avg_order": r[4]}
    for r in cur.fetchall()
]

# 5. Top Drivers
driver_query = """
SELECT 
    d.name,
    COUNT(o.order_id) AS orders,
    ROUND(AVG(o.order_rating), 2) AS rating,
    ROUND(AVG(
        (strftime('%H', o.delivered_time)*60 + strftime('%M', o.delivered_time)) - 
        (strftime('%H', o.order_time)*60 + strftime('%M', o.order_time))
    ), 1) AS avg_mins
FROM orders o
JOIN drivers d ON d.driver_id = o.driver_id
GROUP BY d.driver_id, d.name
HAVING orders >= 50
ORDER BY rating DESC
LIMIT 12;
"""
cur.execute(driver_query)
drivers_data = [
    {"name": r[0], "orders": r[1], "rating": r[2], "avg_mins": r[3]}
    for r in cur.fetchall()
]

conn.close()

# Prepare JSON payloads
payload = {
    "matrix": matrix_data,
    "hourly": hourly_data,
    "dishes": dishes_data,
    "restaurants": restaurants_data,
    "drivers": drivers_data
}

json_str = json.dumps(payload, separators=(',', ':'))

# Build dynamic HTML
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FoodHunter - Dynamic Interactive BI Dashboard</title>
    
    <!-- Meta tags for responsive & social -->
    <meta name="description" content="FoodHunter Interactive Data Analytics & BI Dashboard. Explore revenue trends, cuisine share, dish sales, and delivery efficiency.">
    <meta name="theme-color" content="#4F46E5">
    
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome 6 -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
    <!-- Google Fonts Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>

    <style>
        :root {{
            --bg-body: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --primary: #4f46e5;
            --primary-light: #eef2ff;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #ef4444;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 2px 6px -2px rgba(15, 23, 42, 0.04);
            --shadow-hover: 0 12px 24px -4px rgba(15, 23, 42, 0.12);
        }}

        [data-theme="dark"] {{
            --bg-body: #0b0f19;
            --bg-card: #151c2e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --border-color: #242f47;
            --primary: #6366f1;
            --primary-light: rgba(99, 102, 241, 0.15);
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
            --shadow-md: 0 4px 16px rgba(0,0,0,0.3);
            --shadow-hover: 0 12px 28px rgba(0,0,0,0.5);
        }}

        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-body);
            color: var(--text-main);
            transition: background-color 0.3s ease, color 0.3s ease;
            overflow-x: hidden;
        }}

        /* Navbar */
        .navbar-custom {{
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
            box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }}

        /* Filter Toolbar */
        .filter-bar {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 16px 20px;
            box-shadow: var(--shadow-md);
            margin-bottom: 24px;
        }}

        /* KPI Card */
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 22px;
            box-shadow: var(--shadow-md);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
        }}
        .kpi-card:hover {{
            transform: translateY(-4px);
            box-shadow: var(--shadow-hover);
        }}
        .kpi-icon-box {{
            width: 48px;
            height: 48px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.35rem;
        }}
        .kpi-title {{
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kpi-value {{
            font-size: 1.85rem;
            font-weight: 800;
            color: var(--text-main);
            margin: 6px 0 4px 0;
            letter-spacing: -0.5px;
        }}

        /* Chart Container Cards */
        .chart-box {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 22px;
            box-shadow: var(--shadow-md);
            margin-bottom: 24px;
            transition: box-shadow 0.2s ease;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .chart-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        /* Badges */
        .badge-pill-custom {{
            padding: 5px 12px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 0.78rem;
        }}

        /* Select controls */
        .form-select-custom {{
            background-color: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 8px 14px;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}
        .form-select-custom:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
            background-color: var(--bg-card);
            color: var(--text-main);
        }}

        /* Table styling */
        .table-custom {{
            color: var(--text-main);
        }}
        .table-custom thead th {{
            background-color: var(--primary-light);
            color: var(--primary);
            font-weight: 700;
            font-size: 0.82rem;
            text-transform: uppercase;
            border-bottom: 2px solid var(--border-color);
            padding: 12px 14px;
        }}
        .table-custom tbody td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.9rem;
        }}

        /* Nav Pills for Views */
        .nav-pills .nav-link {{
            color: var(--text-muted);
            border-radius: 12px;
            font-weight: 600;
            padding: 8px 16px;
            transition: all 0.2s;
        }}
        .nav-pills .nav-link.active {{
            background-color: var(--primary);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
        }}

        /* Responsive utilities */
        @media (max-width: 768px) {{
            .kpi-value {{
                font-size: 1.5rem;
            }}
            .filter-bar {{
                padding: 14px;
            }}
        }}
    </style>
</head>
<body data-theme="light">

    <!-- TOP NAVBAR -->
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom py-3 sticky-top">
        <div class="container-fluid px-3 px-md-4">
            <a class="navbar-brand d-flex align-items-center gap-2 fw-bold fs-4 text-white" href="#">
                <span class="p-2 bg-danger rounded-3 text-white"><i class="fas fa-burger"></i></span>
                FoodHunter BI
            </a>
            
            <div class="d-flex align-items-center gap-2 gap-md-3">
                <!-- Theme Toggle Button -->
                <button id="themeToggleBtn" class="btn btn-outline-light btn-sm rounded-pill px-3 fw-semibold" title="Toggle Dark/Light Mode">
                    <i class="fas fa-moon me-1"></i> <span class="d-none d-sm-inline">Dark Mode</span>
                </button>
                
                <!-- GitHub Repo Link -->
                <a href="https://github.com/Sahil-093/foodhunter-case-study" target="_blank" class="btn btn-warning btn-sm rounded-pill px-3 fw-bold text-dark shadow-sm">
                    <i class="fab fa-github me-1"></i> <span class="d-none d-sm-inline">GitHub Repo</span>
                </a>
            </div>
        </div>
    </nav>

    <!-- MAIN CONTAINER -->
    <div class="container-fluid px-3 px-md-4 py-4">

        <!-- INTRO & BREADCRUMB -->
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center mb-3 gap-2">
            <div>
                <h3 class="fw-bolder mb-1" style="letter-spacing: -0.5px;">Interactive Executive Dashboard</h3>
                <p class="text-muted small mb-0">Multi-Dimensional Analysis of 43,118 Orders &bull; June 1 – September 29, 2022</p>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 px-3 py-2 rounded-pill fw-semibold">
                    <i class="fas fa-bolt me-1"></i> Live Real-Time Filtering
                </span>
            </div>
        </div>

        <!-- DYNAMIC FILTER TOOLBAR -->
        <div class="filter-bar">
            <div class="row g-2 align-items-center">
                <div class="col-12 col-sm-6 col-lg-3">
                    <label class="form-label small fw-bold text-muted mb-1"><i class="fas fa-utensils me-1"></i> Cuisine Filter</label>
                    <select id="cuisineSelect" class="form-select form-select-custom">
                        <option value="ALL">All Cuisines (Chinese, Italian, Indian, Thai)</option>
                        <option value="Chinese">Chinese Only</option>
                        <option value="Italian">Italian Only</option>
                        <option value="Indian">Indian Only</option>
                        <option value="Thai">Thai Only</option>
                    </select>
                </div>
                
                <div class="col-12 col-sm-6 col-lg-3">
                    <label class="form-label small fw-bold text-muted mb-1"><i class="fas fa-calendar-alt me-1"></i> Month Filter</label>
                    <select id="monthSelect" class="form-select form-select-custom">
                        <option value="ALL">Full Timeframe (June - Sept 2022)</option>
                        <option value="2022-06">June 2022</option>
                        <option value="2022-07">July 2022</option>
                        <option value="2022-08">August 2022</option>
                        <option value="2022-09">September 2022</option>
                    </select>
                </div>
                
                <div class="col-12 col-sm-6 col-lg-3">
                    <label class="form-label small fw-bold text-muted mb-1"><i class="fas fa-business-time me-1"></i> Day Type</label>
                    <select id="dayTypeSelect" class="form-select form-select-custom">
                        <option value="ALL">All Days (Weekdays & Weekends)</option>
                        <option value="Weekday">Weekdays Only (Mon - Fri)</option>
                        <option value="Weekend">Weekends Only (Sat - Sun)</option>
                    </select>
                </div>

                <div class="col-12 col-sm-6 col-lg-3 d-flex align-items-end gap-2 pt-2 pt-lg-0">
                    <button id="resetFiltersBtn" class="btn btn-outline-secondary w-100 rounded-3 fw-semibold py-2">
                        <i class="fas fa-rotate-left me-1"></i> Reset Filters
                    </button>
                    <button id="exportCsvBtn" class="btn btn-primary w-100 rounded-3 fw-semibold py-2">
                        <i class="fas fa-file-csv me-1"></i> Export CSV
                    </button>
                </div>
            </div>
        </div>

        <!-- DYNAMIC KPI SCORECARDS (Live Updating) -->
        <div class="row g-3 mb-4">
            <!-- KPI 1: Revenue -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">Gross Revenue</span>
                        <div class="kpi-icon-box" style="background:#EEF2FF; color:#4F46E5;">
                            <i class="fas fa-dollar-sign"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiRevenue">$1,197,706</div>
                    <span class="badge-pill-custom bg-primary bg-opacity-10 text-primary" id="kpiOrdersSub">
                        43,118 orders
                    </span>
                </div>
            </div>

            <!-- KPI 2: Total Orders -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">Total Orders</span>
                        <div class="kpi-icon-box" style="background:#ECFDF5; color:#10B981;">
                            <i class="fas fa-bag-shopping"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiOrders">43,118</div>
                    <span class="badge-pill-custom bg-success bg-opacity-10 text-success" id="kpiShareSub">
                        100% of volume
                    </span>
                </div>
            </div>

            <!-- KPI 3: AOV -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">Avg Order Value</span>
                        <div class="kpi-icon-box" style="background:#FFFBEB; color:#F59E0B;">
                            <i class="fas fa-receipt"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiAov">$27.78</div>
                    <span class="badge-pill-custom bg-warning bg-opacity-10 text-warning">
                        Consistent spend
                    </span>
                </div>
            </div>

            <!-- KPI 4: Food Total -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">Food Total</span>
                        <div class="kpi-icon-box" style="background:#F5F3FF; color:#8B5CF6;">
                            <i class="fas fa-plate-wheat"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiFoodTotal">$1,229,527</div>
                    <span class="badge-pill-custom bg-info bg-opacity-10 text-info" id="kpiDiscountSub">
                        13.3% discount
                    </span>
                </div>
            </div>

            <!-- KPI 5: Delivery SLA -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">On-Time (&lt;30m)</span>
                        <div class="kpi-icon-box" style="background:#F0FDF4; color:#16A34A;">
                            <i class="fas fa-stopwatch-20"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiFastPct">82.9%</div>
                    <span class="badge-pill-custom bg-success bg-opacity-10 text-success" id="kpiAvgTimeSub">
                        Avg: 23.4 mins
                    </span>
                </div>
            </div>

            <!-- KPI 6: Delivery Fees -->
            <div class="col-12 col-sm-6 col-xl-2">
                <div class="kpi-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="kpi-title">Delivery Fees</span>
                        <div class="kpi-icon-box" style="background:#FEF2F2; color:#EF4444;">
                            <i class="fas fa-motorcycle"></i>
                        </div>
                    </div>
                    <div class="kpi-value" id="kpiDelivFees">$131,859</div>
                    <span class="badge-pill-custom bg-danger bg-opacity-10 text-danger">
                        250 couriers active
                    </span>
                </div>
            </div>
        </div>

        <!-- TABS BAR FOR MULTI-PERSPECTIVE ANALYTICS -->
        <ul class="nav nav-pills mb-4 gap-2" id="dashboardTabs" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="overview-tab" data-bs-toggle="pill" data-bs-target="#tab-overview" type="button">
                    <i class="fas fa-chart-line me-1"></i> Revenue & Volume Dynamics
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="cuisines-tab" data-bs-toggle="pill" data-bs-target="#tab-cuisines" type="button">
                    <i class="fas fa-bowl-rice me-1"></i> Cuisine & Restaurants
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="dishes-tab" data-bs-toggle="pill" data-bs-target="#tab-dishes" type="button">
                    <i class="fas fa-utensils me-1"></i> Top Dishes & Menu
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="delivery-tab" data-bs-toggle="pill" data-bs-target="#tab-delivery" type="button">
                    <i class="fas fa-truck-fast me-1"></i> Delivery SLA & Drivers
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="table-tab" data-bs-toggle="pill" data-bs-target="#tab-table" type="button">
                    <i class="fas fa-table-list me-1"></i> Live Data Explorer
                </button>
            </li>
        </ul>

        <!-- TAB CONTENT PANES -->
        <div class="tab-content" id="dashboardTabsContent">

            <!-- TAB 1: OVERVIEW & TRENDS -->
            <div class="tab-pane fade show active" id="tab-overview">
                <div class="row g-4">
                    <!-- Monthly Trend Combo Chart -->
                    <div class="col-12 col-xl-8">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-chart-column text-primary"></i>
                                    Monthly Revenue & Order Volume Progression
                                </div>
                                <span class="badge bg-light text-dark border">Dual Axis (Revenue + Orders)</span>
                            </div>
                            <div id="chartMonthly" style="min-height: 380px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Cuisine Share Donut -->
                    <div class="col-12 col-xl-4">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-chart-pie text-success"></i>
                                    Revenue Distribution by Cuisine
                                </div>
                            </div>
                            <div id="chartCuisinePie" style="min-height: 380px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- 24-Hour Peak Demand Curve -->
                    <div class="col-12">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-clock text-info"></i>
                                    24-Hour Peak Ordering Patterns (Hourly Traffic Distribution)
                                </div>
                                <span class="badge bg-light text-dark border">Lunch Peak (12-14h) &bull; Dinner Peak (18-20h)</span>
                            </div>
                            <div id="chartHourly" style="min-height: 320px; width: 100%;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: CUISINES & RESTAURANTS -->
            <div class="tab-pane fade" id="tab-cuisines">
                <div class="row g-4">
                    <!-- Cuisine Comparison Bar -->
                    <div class="col-12 col-lg-6">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-ranking-star text-warning"></i>
                                    Average Order Value by Cuisine ($)
                                </div>
                            </div>
                            <div id="chartCuisineBar" style="min-height: 360px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Day Type Comparison -->
                    <div class="col-12 col-lg-6">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-calendar-week text-danger"></i>
                                    Weekday vs Weekend Volume & Spend
                                </div>
                            </div>
                            <div id="chartDayType" style="min-height: 360px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Top 10 Restaurants Leaderboard -->
                    <div class="col-12">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-store text-primary"></i>
                                    Top 10 Performing Restaurants by Revenue
                                </div>
                            </div>
                            <div id="chartRestaurants" style="min-height: 400px; width: 100%;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: DISHES & MENU -->
            <div class="tab-pane fade" id="tab-dishes">
                <div class="row g-4">
                    <!-- Top Dishes Bar -->
                    <div class="col-12 col-xl-8">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-fire text-danger"></i>
                                    Top 12 Most Ordered Dishes (Units Sold)
                                </div>
                                <span class="badge bg-light text-dark border">Dynamically filters by Cuisine</span>
                            </div>
                            <div id="chartDishes" style="min-height: 420px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Veg vs Non-Veg Share -->
                    <div class="col-12 col-xl-4">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-leaf text-success"></i>
                                    Dietary Split (Veg vs Non-Veg)
                                </div>
                            </div>
                            <div id="chartDietary" style="min-height: 420px; width: 100%;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: DELIVERY & LOGISTICS -->
            <div class="tab-pane fade" id="tab-delivery">
                <div class="row g-4">
                    <!-- SLA Pie -->
                    <div class="col-12 col-lg-5">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-stopwatch text-success"></i>
                                    Delivery SLA Compliance
                                </div>
                            </div>
                            <div id="chartDeliverySLA" style="min-height: 360px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Top Drivers Table -->
                    <div class="col-12 col-lg-7">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div class="chart-title">
                                    <i class="fas fa-medal text-warning"></i>
                                    Top Rated Courier Fleet (Rating &gt;= 3.7 & Min 50 Orders)
                                </div>
                            </div>
                            <div class="table-responsive" style="max-height: 360px; overflow-y: auto;">
                                <table class="table table-hover table-custom align-middle mb-0">
                                    <thead>
                                        <tr>
                                            <th>Courier Name</th>
                                            <th>Orders Fulfilled</th>
                                            <th>Avg Rating</th>
                                            <th>Avg Speed</th>
                                        </tr>
                                    </thead>
                                    <tbody id="driverTableBody">
                                        <!-- Dynamically Populated -->
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 5: DATA EXPLORER -->
            <div class="tab-pane fade" id="tab-table">
                <div class="chart-box">
                    <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2 mb-3">
                        <div class="chart-title">
                            <i class="fas fa-magnifying-glass text-primary"></i>
                            Live Searchable Restaurant & Menu Records
                        </div>
                        <div style="min-width: 280px;">
                            <input type="text" id="tableSearchInput" class="form-control form-control-sm rounded-pill px-3" placeholder="Search restaurant, dish, or cuisine...">
                        </div>
                    </div>
                    <div class="table-responsive" style="max-height: 480px; overflow-y: auto;">
                        <table class="table table-hover table-custom align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>Restaurant Name</th>
                                    <th>Cuisine</th>
                                    <th>Orders Completed</th>
                                    <th>Total Revenue</th>
                                    <th>Average Ticket</th>
                                </tr>
                            </thead>
                            <tbody id="explorerTableBody">
                                <!-- Populated by JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

        </div> <!-- End tab-content -->

        <!-- FOOTER -->
        <footer class="text-center py-4 text-muted small border-top mt-4">
            <p class="mb-1 fw-bold">FoodHunter Data Analytics Hub &bull; Powered by Python, Pandas, SQLite & Plotly.js</p>
            <p class="mb-0">Interactive &bull; Dynamic &bull; Fully Responsive Client-Side BI Platform</p>
        </footer>

    </div> <!-- End container -->

    <!-- Bootstrap 5 JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

    <!-- EMBEDDED REAL DATASET -->
    <script>
        const RAW_DATA = {json_str};

        // Theme Toggle
        const themeBtn = document.getElementById('themeToggleBtn');
        let currentTheme = 'light';
        themeBtn.addEventListener('click', () => {{
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.body.setAttribute('data-theme', currentTheme);
            themeBtn.innerHTML = currentTheme === 'dark' 
                ? '<i class="fas fa-sun me-1"></i> <span class="d-none d-sm-inline">Light Mode</span>' 
                : '<i class="fas fa-moon me-1"></i> <span class="d-none d-sm-inline">Dark Mode</span>';
            renderAllCharts();
        }});

        // Filter elements
        const cuisineSel = document.getElementById('cuisineSelect');
        const monthSel = document.getElementById('monthSelect');
        const dayTypeSel = document.getElementById('dayTypeSelect');
        const resetBtn = document.getElementById('resetFiltersBtn');
        const exportBtn = document.getElementById('exportCsvBtn');
        const searchInput = document.getElementById('tableSearchInput');

        // Events
        cuisineSel.addEventListener('change', updateDashboard);
        monthSel.addEventListener('change', updateDashboard);
        dayTypeSel.addEventListener('change', updateDashboard);
        resetBtn.addEventListener('click', () => {{
            cuisineSel.value = 'ALL';
            monthSel.value = 'ALL';
            dayTypeSel.value = 'ALL';
            updateDashboard();
        }});
        searchInput.addEventListener('input', filterExplorerTable);

        // Export to CSV
        exportBtn.addEventListener('click', () => {{
            const filtered = getFilteredMatrix();
            let csv = "Month,Cuisine,Day_Type,Orders,Revenue,Food_Total,Delivery_Fees,Discounts,Avg_Delivery_Mins\\n";
            filtered.forEach(r => {{
                csv += `${{r.month}},${{r.cuisine}},${{r.day_type}},${{r.orders}},${{r.revenue}},${{r.food_total}},${{r.deliv_fee}},${{r.discount}},${{r.avg_deliv}}\\n`;
            }});
            const blob = new Blob([csv], {{ type: 'text/csv' }});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.setAttribute('href', url);
            a.setAttribute('download', `foodhunter_filtered_data_${{Date.now()}}.csv`);
            a.click();
        }});

        function getFilteredMatrix() {{
            const cVal = cuisineSel.value;
            const mVal = monthSel.value;
            const dVal = dayTypeSel.value;

            return RAW_DATA.matrix.filter(r => {{
                if (cVal !== 'ALL' && r.cuisine !== cVal) return false;
                if (mVal !== 'ALL' && r.month !== mVal) return false;
                if (dVal !== 'ALL' && r.day_type !== dVal) return false;
                return true;
            }});
        }}

        function getPlotlyTemplate() {{
            return currentTheme === 'dark' ? 'plotly_dark' : 'plotly_white';
        }}

        function updateDashboard() {{
            const data = getFilteredMatrix();

            // Calculate Aggregates
            let totalRev = 0, totalOrders = 0, foodTot = 0, delivFees = 0, discounts = 0;
            let fastDeliv = 0, totalDelivCount = 0;

            data.forEach(r => {{
                totalRev += r.revenue;
                totalOrders += r.orders;
                foodTot += r.food_total;
                delivFees += r.deliv_fee;
                discounts += r.discount;
                fastDeliv += r.fast_deliv;
                totalDelivCount += r.orders;
            }});

            const aov = totalOrders > 0 ? (totalRev / totalOrders) : 0;
            const fastPct = totalDelivCount > 0 ? ((fastDeliv / totalDelivCount) * 100) : 0;
            const discPct = foodTot > 0 ? ((discounts / foodTot) * 100) : 0;

            // Update KPI DOM
            document.getElementById('kpiRevenue').innerText = '$' + totalRev.toLocaleString('en-US', {{maximumFractionDigits: 0}});
            document.getElementById('kpiOrders').innerText = totalOrders.toLocaleString('en-US');
            document.getElementById('kpiOrdersSub').innerText = totalOrders.toLocaleString('en-US') + ' orders';
            document.getElementById('kpiAov').innerText = '$' + aov.toFixed(2);
            document.getElementById('kpiFoodTotal').innerText = '$' + foodTot.toLocaleString('en-US', {{maximumFractionDigits: 0}});
            document.getElementById('kpiDiscountSub').innerText = discPct.toFixed(1) + '% discount share';
            document.getElementById('kpiFastPct').innerText = fastPct.toFixed(1) + '%';
            document.getElementById('kpiDelivFees').innerText = '$' + delivFees.toLocaleString('en-US', {{maximumFractionDigits: 0}});

            renderAllCharts();
            populateDriversTable();
            populateExplorerTable();
        }}

        function renderAllCharts() {{
            renderMonthlyChart();
            renderCuisinePie();
            renderHourlyChart();
            renderCuisineBar();
            renderDayTypeChart();
            renderRestaurantsChart();
            renderDishesChart();
            renderDietaryChart();
            renderDeliverySLA();
        }}

        // 1. Monthly Chart
        function renderMonthlyChart() {{
            const filtered = getFilteredMatrix();
            const months = ['2022-06', '2022-07', '2022-08', '2022-09'];
            const revMap = {{}}, ordMap = {{}};
            months.forEach(m => {{ revMap[m] = 0; ordMap[m] = 0; }});

            filtered.forEach(r => {{
                if (revMap[r.month] !== undefined) {{
                    revMap[r.month] += r.revenue;
                    ordMap[r.month] += r.orders;
                }}
            }});

            const xVals = ['June 2022', 'July 2022', 'August 2022', 'September 2022'];
            const yRev = months.map(m => revMap[m]);
            const yOrd = months.map(m => ordMap[m]);

            const traceRev = {{
                x: xVals,
                y: yRev,
                name: 'Revenue ($)',
                type: 'bar',
                marker: {{ color: '#4F46E5', opacity: 0.9 }},
                text: yRev.map(v => '$' + Math.round(v).toLocaleString()),
                textposition: 'inside'
            }};

            const traceOrd = {{
                x: xVals,
                y: yOrd,
                name: 'Orders Count',
                type: 'scatter',
                mode: 'lines+markers+text',
                yaxis: 'y2',
                line: {{ color: '#F59E0B', width: 3 }},
                marker: {{ size: 8, color: '#F59E0B' }},
                text: yOrd.map(v => v.toLocaleString()),
                textposition: 'top center'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 40, t: 30, b: 40 }},
                legend: {{ orientation: 'h', y: 1.12, x: 0.5, xanchor: 'center' }},
                yaxis: {{ title: 'Revenue ($)', showgrid: true }},
                yaxis2: {{ title: 'Order Volume', overlaying: 'y', side: 'right', showgrid: false }},
                autosize: true
            }};

            Plotly.react('chartMonthly', [traceRev, traceOrd], layout, {{ responsive: true }});
        }}

        // 2. Cuisine Pie
        function renderCuisinePie() {{
            const filtered = getFilteredMatrix();
            const cuisMap = {{}};
            filtered.forEach(r => {{
                cuisMap[r.cuisine] = (cuisMap[r.cuisine] || 0) + r.revenue;
            }});

            const labels = Object.keys(cuisMap);
            const values = Object.values(cuisMap);

            const trace = {{
                labels: labels,
                values: values,
                type: 'pie',
                hole: 0.48,
                marker: {{ colors: ['#4F46E5', '#10B981', '#F59E0B', '#EF4444'] }},
                textinfo: 'label+percent',
                hoverinfo: 'label+value+percent'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 20, r: 20, t: 20, b: 20 }},
                showlegend: false,
                autosize: true
            }};

            Plotly.react('chartCuisinePie', [trace], layout, {{ responsive: true }});
        }}

        // 3. Hourly Curve
        function renderHourlyChart() {{
            const cVal = cuisineSel.value;
            const hourlyMap = new Array(24).fill(0);

            RAW_DATA.hourly.forEach(r => {{
                if (cVal === 'ALL' || r.cuisine === cVal) {{
                    hourlyMap[r.hour] += r.orders;
                }}
            }});

            const hours = Array.from({{length: 24}}, (_, i) => i + ':00');

            const trace = {{
                x: hours,
                y: hourlyMap,
                type: 'scatter',
                mode: 'lines',
                fill: 'tozeroy',
                line: {{ color: '#6366F1', width: 3 }},
                fillcolor: currentTheme === 'dark' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(79, 70, 229, 0.12)'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 20, t: 20, b: 40 }},
                xaxis: {{ title: 'Hour of Day (24-Hour Cycle)' }},
                yaxis: {{ title: 'Orders Placed' }},
                autosize: true
            }};

            Plotly.react('chartHourly', [trace], layout, {{ responsive: true }});
        }}

        // 4. Cuisine AOV Bar
        function renderCuisineBar() {{
            const filtered = getFilteredMatrix();
            const cuisRev = {{}}, cuisOrd = {{}};
            filtered.forEach(r => {{
                cuisRev[r.cuisine] = (cuisRev[r.cuisine] || 0) + r.revenue;
                cuisOrd[r.cuisine] = (cuisOrd[r.cuisine] || 0) + r.orders;
            }});

            const cuisines = Object.keys(cuisRev);
            const aovs = cuisines.map(c => cuisOrd[c] > 0 ? (cuisRev[c] / cuisOrd[c]) : 0);

            const trace = {{
                x: cuisines,
                y: aovs,
                type: 'bar',
                marker: {{ color: ['#4F46E5', '#10B981', '#F59E0B', '#EF4444'] }},
                text: aovs.map(v => '$' + v.toFixed(2)),
                textposition: 'outside'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 20, t: 20, b: 40 }},
                yaxis: {{ title: 'Average Ticket ($)' }},
                autosize: true
            }};

            Plotly.react('chartCuisineBar', [trace], layout, {{ responsive: true }});
        }}

        // 5. Day Type Comparison
        function renderDayTypeChart() {{
            const filtered = getFilteredMatrix();
            let wkRev = 0, weRev = 0;
            let wkOrd = 0, weOrd = 0;

            filtered.forEach(r => {{
                if (r.day_type === 'Weekday') {{
                    wkRev += r.revenue;
                    wkOrd += r.orders;
                }} else {{
                    weRev += r.revenue;
                    weOrd += r.orders;
                }}
            }});

            const trace = {{
                x: ['Weekdays (Mon-Fri)', 'Weekends (Sat-Sun)'],
                y: [wkRev, weRev],
                type: 'bar',
                marker: {{ color: ['#3B82F6', '#EC4899'] }},
                text: ['$' + Math.round(wkRev).toLocaleString(), '$' + Math.round(weRev).toLocaleString()],
                textposition: 'inside'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 20, t: 20, b: 40 }},
                yaxis: {{ title: 'Revenue ($)' }},
                autosize: true
            }};

            Plotly.react('chartDayType', [trace], layout, {{ responsive: true }});
        }}

        // 6. Restaurants Chart
        function renderRestaurantsChart() {{
            const cVal = cuisineSel.value;
            let list = RAW_DATA.restaurants;
            if (cVal !== 'ALL') {{
                list = list.filter(r => r.cuisine === cVal);
            }}
            const top10 = list.slice(0, 10).reverse();

            const trace = {{
                x: top10.map(r => r.revenue),
                y: top10.map(r => r.name),
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '#4F46E5' }},
                text: top10.map(r => '$' + Math.round(r.revenue).toLocaleString()),
                textposition: 'outside'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 160, r: 50, t: 20, b: 40 }},
                xaxis: {{ title: 'Revenue ($)' }},
                autosize: true
            }};

            Plotly.react('chartRestaurants', [trace], layout, {{ responsive: true }});
        }}

        // 7. Dishes Chart
        function renderDishesChart() {{
            const cVal = cuisineSel.value;
            let list = RAW_DATA.dishes;
            if (cVal !== 'ALL') {{
                list = list.filter(d => d.cuisine === cVal);
            }}
            const top12 = list.slice(0, 12).reverse();

            const trace = {{
                x: top12.map(d => d.qty),
                y: top12.map(d => d.name),
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '#EF4444' }},
                text: top12.map(d => d.qty.toLocaleString() + ' units'),
                textposition: 'inside'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 170, r: 40, t: 20, b: 40 }},
                xaxis: {{ title: 'Units Sold' }},
                autosize: true
            }};

            Plotly.react('chartDishes', [trace], layout, {{ responsive: true }});
        }}

        // 8. Dietary Split Chart
        function renderDietaryChart() {{
            const cVal = cuisineSel.value;
            let veg = 0, nonVeg = 0;
            RAW_DATA.dishes.forEach(d => {{
                if (cVal === 'ALL' || d.cuisine === cVal) {{
                    if (d.category === 'Vegetarian') veg += d.qty;
                    else nonVeg += d.qty;
                }}
            }});

            const trace = {{
                labels: ['Vegetarian', 'Non-Vegetarian'],
                values: [veg, nonVeg],
                type: 'pie',
                hole: 0.45,
                marker: {{ colors: ['#10B981', '#EF4444'] }}
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 20, r: 20, t: 20, b: 20 }},
                showlegend: true,
                legend: {{ orientation: 'h', y: -0.1 }},
                autosize: true
            }};

            Plotly.react('chartDietary', [trace], layout, {{ responsive: true }});
        }}

        // 9. Delivery SLA Chart
        function renderDeliverySLA() {{
            const filtered = getFilteredMatrix();
            let fast = 0, mod = 0;
            filtered.forEach(r => {{
                fast += r.fast_deliv;
                mod += r.mod_deliv;
            }});

            const trace = {{
                labels: ['Under 30 Mins (Fast)', '30 - 44 Mins (Moderate)'],
                values: [fast, mod],
                type: 'pie',
                hole: 0.5,
                marker: {{ colors: ['#10B981', '#F59E0B'] }}
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 20, r: 20, t: 20, b: 20 }},
                showlegend: true,
                legend: {{ orientation: 'h', y: -0.1 }},
                autosize: true
            }};

            Plotly.react('chartDeliverySLA', [trace], layout, {{ responsive: true }});
        }}

        // Drivers Table
        function populateDriversTable() {{
            const body = document.getElementById('driverTableBody');
            body.innerHTML = RAW_DATA.drivers.map(d => `
                <tr>
                    <td><strong>${{d.name}}</strong></td>
                    <td><span class="badge bg-primary bg-opacity-10 text-primary">${{d.orders}} orders</span></td>
                    <td><span class="badge bg-warning text-dark"><i class="fas fa-star me-1"></i>${{d.rating}}</span></td>
                    <td><span class="text-muted">${{d.avg_mins}} mins</span></td>
                </tr>
            `).join('');
        }}

        // Explorer Table
        function populateExplorerTable() {{
            const cVal = cuisineSel.value;
            let list = RAW_DATA.restaurants;
            if (cVal !== 'ALL') {{
                list = list.filter(r => r.cuisine === cVal);
            }}

            const body = document.getElementById('explorerTableBody');
            body.innerHTML = list.slice(0, 50).map(r => `
                <tr>
                    <td><strong>${{r.name}}</strong></td>
                    <td><span class="badge bg-secondary bg-opacity-10 text-secondary">${{r.cuisine}}</span></td>
                    <td>${{r.orders.toLocaleString()}}</td>
                    <td><strong>$${{Math.round(r.revenue).toLocaleString()}}</strong></td>
                    <td>$${{r.avg_order.toFixed(2)}}</td>
                </tr>
            `).join('');
        }}

        function filterExplorerTable() {{
            const q = searchInput.value.toLowerCase();
            const rows = document.querySelectorAll('#explorerTableBody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                r.style.display = text.includes(q) ? '' : 'none';
            }});
        }}

        // Responsive Resize Handler
        window.addEventListener('resize', () => {{
            const chartIds = [
                'chartMonthly', 'chartCuisinePie', 'chartHourly', 
                'chartCuisineBar', 'chartDayType', 'chartRestaurants', 
                'chartDishes', 'chartDietary', 'chartDeliverySLA'
            ];
            chartIds.forEach(id => {{
                const el = document.getElementById(id);
                if (el && el.data) {{
                    Plotly.Plots.resize(el);
                }}
            }});
        }});

        // Trigger resize on tab switch so charts render with perfect geometry
        document.querySelectorAll('button[data-bs-toggle="pill"]').forEach(tab => {{
            tab.addEventListener('shown.bs.tab', () => {{
                window.dispatchEvent(new Event('resize'));
            }});
        }});

        // Initial Load
        updateDashboard();
    </script>
</body>
</html>
"""

with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"[SUCCESS] Ultra-dynamic interactive responsive dashboard compiled at: {output_html}")
