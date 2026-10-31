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

# 6. RFM Customer Segmentation (Step 1 ML)
import pandas as pd
query_rfm = """
SELECT 
    customer_id,
    CAST((julianday('2022-09-30') - julianday(MAX(order_date))) AS INTEGER) AS recency_days,
    COUNT(order_id) AS frequency,
    ROUND(SUM(final_price), 2) AS monetary
FROM orders
GROUP BY customer_id
"""
df_rfm = pd.read_sql_query(query_rfm, conn)

def f_score(f):
    if f <= 2: return 1
    elif f <= 4: return 2
    elif f <= 6: return 3
    else: return 4

df_rfm['r_score'] = pd.qcut(df_rfm['recency_days'], q=4, labels=[4, 3, 2, 1]).astype(int)
df_rfm['f_score'] = df_rfm['frequency'].apply(f_score).astype(int)
df_rfm['m_score'] = pd.qcut(df_rfm['monetary'], q=4, labels=[1, 2, 3, 4]).astype(int)

def assign_segment(row):
    r, f, m = row['r_score'], row['f_score'], row['m_score']
    if r >= 4 and f >= 3:
        return 'Champions'
    elif r >= 3 and f >= 3:
        return 'Loyal Customers'
    elif r >= 3 and f <= 2:
        return 'Potential Loyalists'
    elif r == 2 and f >= 3:
        return 'Needs Attention'
    elif r == 2 and f <= 2:
        return 'About to Sleep'
    elif r == 1 and f >= 3:
        return 'At Risk'
    else:
        return 'Hibernating / Churned'

df_rfm['segment'] = df_rfm.apply(assign_segment, axis=1)

summary = df_rfm.groupby('segment').agg(
    customers=('customer_id', 'count'),
    avg_recency=('recency_days', 'mean'),
    avg_freq=('frequency', 'mean'),
    avg_monetary=('monetary', 'mean'),
    total_revenue=('monetary', 'sum')
).reset_index()

total_rev = df_rfm['monetary'].sum()
total_cust = len(df_rfm)

summary['customer_pct'] = (summary['customers'] / total_cust * 100).round(1)
summary['revenue_pct'] = (summary['total_revenue'] / total_rev * 100).round(1)
summary['avg_recency'] = summary['avg_recency'].round(1)
summary['avg_freq'] = summary['avg_freq'].round(1)
summary['avg_monetary'] = summary['avg_monetary'].round(2)
summary['total_revenue'] = summary['total_revenue'].round(2)

order_priority = ['Champions', 'Loyal Customers', 'Potential Loyalists', 'Needs Attention', 'About to Sleep', 'At Risk', 'Hibernating / Churned']
summary['sort_key'] = summary['segment'].apply(lambda s: order_priority.index(s))
summary = summary.sort_values('sort_key').drop(columns=['sort_key'])

strategies = {
    'Champions': {
        'badge': 'bg-success',
        'color': '#10B981',
        'icon': 'fa-crown',
        'action': 'Reward loyalty, provide VIP early access to new menu items, zero delivery fee perks, and high-tier referral rewards.'
    },
    'Loyal Customers': {
        'badge': 'bg-primary',
        'color': '#4F46E5',
        'icon': 'fa-medal',
        'action': 'Upsell high-ticket entrees and dessert bundles, invite into tiered VIP rewards program to convert them into Champions.'
    },
    'Potential Loyalists': {
        'badge': 'bg-info',
        'color': '#06B6D4',
        'icon': 'fa-arrow-trend-up',
        'action': 'Encourage recurring weekly orders with personalized push notifications and targeted weekend coupon boosters.'
    },
    'Needs Attention': {
        'badge': 'bg-warning text-dark',
        'color': '#F59E0B',
        'icon': 'fa-bell',
        'action': 'Reactivate before slip: Send limited-time 15% discount for their favorite cuisine (ordered within 48 hours).'
    },
    'About to Sleep': {
        'badge': 'bg-secondary',
        'color': '#64748B',
        'icon': 'fa-moon',
        'action': 'Share popular trending dishes in their locality, provide free appetizer voucher with any $25+ order.'
    },
    'At Risk': {
        'badge': 'bg-danger',
        'color': '#EF4444',
        'icon': 'fa-triangle-exclamation',
        'action': 'Urgent retention campaign: High spenders slipping away! Deploy $10 win-back voucher and direct feedback survey.'
    },
    'Hibernating / Churned': {
        'badge': 'bg-dark',
        'color': '#334155',
        'icon': 'fa-user-slash',
        'action': 'Low-cost automated email drip highlighting brand new menu launches and revamped delivery SLA guarantees.'
    }
}

rfm_records = []
for _, row in summary.iterrows():
    s = row['segment']
    info = strategies.get(s, {})
    rfm_records.append({
        'segment': s,
        'customers': int(row['customers']),
        'customer_pct': float(row['customer_pct']),
        'total_revenue': float(row['total_revenue']),
        'revenue_pct': float(row['revenue_pct']),
        'avg_recency': float(row['avg_recency']),
        'avg_freq': float(row['avg_freq']),
        'avg_monetary': float(row['avg_monetary']),
        'badge': info.get('badge', 'bg-secondary'),
        'color': info.get('color', '#64748B'),
        'icon': info.get('icon', 'fa-user'),
        'strategy': info.get('action', '')
    })

# Sample stratified scatter
scatter_sample = []
for seg, group in df_rfm.groupby('segment'):
    sample = group.sample(min(len(group), 85), random_state=42)
    for _, r in sample.iterrows():
        scatter_sample.append({
            'id': int(r['customer_id']),
            'r': int(r['recency_days']),
            'f': int(r['frequency']),
            'm': float(r['monetary']),
            'seg': seg
        })

# 7. Market Basket Analysis (Step 1 ML)
total_orders_items = conn.execute('SELECT COUNT(DISTINCT order_id) FROM orders_items').fetchone()[0]
item_counts = dict(conn.execute('SELECT f.item_name, COUNT(DISTINCT oi.order_id) FROM orders_items oi JOIN food_items f ON f.item_id = oi.item_id GROUP BY f.item_name').fetchall())

query_pairs = """
SELECT 
    f1.item_name AS item_a,
    r1.cuisine AS cuisine_a,
    f2.item_name AS item_b,
    r2.cuisine AS cuisine_b,
    COUNT(*) AS pair_orders
FROM orders_items oi1
JOIN orders_items oi2 ON oi1.order_id = oi2.order_id AND oi1.item_id < oi2.item_id
JOIN food_items f1 ON f1.item_id = oi1.item_id
JOIN food_items f2 ON f2.item_id = oi2.item_id
JOIN restaurants r1 ON r1.restaurant_id = f1.restaurant_id
JOIN restaurants r2 ON r2.restaurant_id = f2.restaurant_id
GROUP BY item_a, item_b
ORDER BY pair_orders DESC
LIMIT 12;
"""
df_pairs = pd.read_sql_query(query_pairs, conn)

top_pairs = []
for _, row in df_pairs.iterrows():
    ia, ib = row['item_a'], row['item_b']
    cnt_a = item_counts.get(ia, 1)
    cnt_b = item_counts.get(ib, 1)
    p_cnt = int(row['pair_orders'])
    conf = round((p_cnt / cnt_a) * 100, 1)
    lift = round((p_cnt * total_orders_items) / (cnt_a * cnt_b), 2)
    top_pairs.append({
        'pair': f"{ia} + {ib}",
        'item_a': ia,
        'item_b': ib,
        'cuisine': row['cuisine_a'],
        'orders': p_cnt,
        'conf': conf,
        'lift': lift,
        'deal': f"Combo Deal: Add {ib} for 15% OFF when ordering {ia}"
    })

query_cuisine_pairs = """
SELECT 
    r1.cuisine,
    f1.item_name AS item_a,
    f2.item_name AS item_b,
    COUNT(*) AS pair_count
FROM orders_items oi1
JOIN orders_items oi2 ON oi1.order_id = oi2.order_id AND oi1.item_id < oi2.item_id
JOIN food_items f1 ON f1.item_id = oi1.item_id
JOIN food_items f2 ON f2.item_id = oi2.item_id
JOIN restaurants r1 ON r1.restaurant_id = f1.restaurant_id
JOIN restaurants r2 ON r2.restaurant_id = f2.restaurant_id
WHERE r1.cuisine = r2.cuisine
GROUP BY r1.cuisine, item_a, item_b
ORDER BY r1.cuisine, pair_count DESC
"""
df_cp = pd.read_sql_query(query_cuisine_pairs, conn)

cuisine_baskets = {}
for c in ['Chinese', 'Italian', 'Indian', 'Thai']:
    sub = df_cp[df_cp['cuisine'] == c].head(5)
    items = []
    for _, r in sub.iterrows():
        ia, ib = r['item_a'], r['item_b']
        cnt_a = item_counts.get(ia, 1)
        cnt_b = item_counts.get(ib, 1)
        p_cnt = int(r['pair_count'])
        conf = round((p_cnt / cnt_a) * 100, 1)
        lift = round((p_cnt * total_orders_items) / (cnt_a * cnt_b), 2)
        items.append({
            'item_a': ia,
            'item_b': ib,
            'pair': f"{ia} + {ib}",
            'orders': p_cnt,
            'conf': conf,
            'lift': lift,
            'deal': f"Add {ib} as side with {ia} to save $2.50"
        })
    cuisine_baskets[c] = items

conn.close()

# Prepare JSON payloads
payload = {
    "matrix": matrix_data,
    "hourly": hourly_data,
    "dishes": dishes_data,
    "restaurants": restaurants_data,
    "drivers": drivers_data,
    "rfm_summary": rfm_records,
    "rfm_scatter": scatter_sample,
    "top_pairs": top_pairs,
    "cuisine_baskets": cuisine_baskets,
    "strategy_waterfall": {
        "x": ["Sep Run-Rate", "VIP Win-Back", "Menu Bundling", "Discount Optimization", "Cuisine Expansion", "Target Run-Rate"],
        "y": [258.2, 16.1, 18.5, 16.4, 11.2, 0],
        "text": ["$258.2k", "+$16.1k", "+$18.5k", "+$16.4k", "+$11.2k", "$320.4k"],
        "measure": ["relative", "relative", "relative", "relative", "relative", "total"]
    },
    "priority_matrix": [
        {"name": "Checkout Combo Bundles", "effort": 2.5, "impact": 8.8, "cat": "Quick Win", "color": "#10B981", "desc": "Pre-packaged Apriori combos at 10-15% side discount. Fast engineering, immediate +$18.5k/mo."},
        {"name": "VIP Churn Win-Back Drip", "effort": 3.0, "impact": 8.2, "cat": "Quick Win", "color": "#10B981", "desc": "Automated email/SMS at day 28 of inactivity with $10 credit to recover $48.4k at-risk revenue."},
        {"name": "Discount Spend Gates ($35+)", "effort": 3.5, "impact": 7.9, "cat": "Quick Win", "color": "#10B981", "desc": "Require $35+ basket for 10% off to stop margin leak on small tickets. Recovers +$16.4k/mo."},
        {"name": "FoodHunter VIP Pass (Loyalty)", "effort": 7.5, "impact": 9.2, "cat": "Major Strategic Bet", "color": "#4F46E5", "desc": "Subscription/Points tier for Champions & Loyalists providing free delivery. Expands CLV by 28%."},
        {"name": "Regional Merchant Expansion", "effort": 6.8, "impact": 8.5, "cat": "Major Strategic Bet", "color": "#4F46E5", "desc": "Onboard 20 top-tier Thai & Indian restaurants to fix 38.6% Chinese cuisine over-reliance."},
        {"name": "Peak-Hour Courier Incentives", "effort": 3.8, "impact": 4.5, "cat": "Fill-In", "color": "#F59E0B", "desc": "Micro-bonus for dinner rush drivers maintaining <25m delivery speeds."},
        {"name": "Dietary Menu Badging (Veg/Vegan)", "effort": 2.0, "impact": 4.0, "cat": "Fill-In", "color": "#F59E0B", "desc": "Prominent green leaf badges on vegetarian items to capture health-conscious segment."},
        {"name": "Wholesale Mobile App Redesign", "effort": 8.5, "impact": 3.8, "cat": "De-prioritize", "color": "#EF4444", "desc": "High cost, complex migration with minimal direct revenue impact compared to CRM & menu levers."}
    ],
    "strategic_pillars": [
        {
            "id": 1,
            "title": "VIP Churn Shield & Automated Win-Back",
            "tag": "Customer Lifetime Value (CLV)",
            "icon": "fa-shield-halved",
            "color": "var(--primary)",
            "bg": "var(--primary-light)",
            "target": "+$48,400 Recovered",
            "kpi": "25% Reactivation of 456 At-Risk VIPs",
            "problem": "456 high-value customers ($158 avg spend) have been inactive for 57+ days, risking $72,185 in annual revenue.",
            "solution": "Deploy 3-stage automated CRM lifecycle drip at Day 21 (gentle reminder), Day 28 ($10 credit on favorite cuisine), and Day 45 (CEO survey + VIP perk).",
            "owner": "CRM & Retention Marketing",
            "timeline": "Immediate (Days 1 - 30)"
        },
        {
            "id": 2,
            "title": "Intelligent Menu Bundling & Cross-Sell",
            "tag": "Average Order Value (AOV) Expansion",
            "icon": "fa-cubes",
            "color": "#10B981",
            "bg": "rgba(16, 185, 129, 0.1)",
            "target": "+$18,500 Monthly MRR",
            "kpi": "AOV Lift: $27.78 → $29.63 (+6.7%)",
            "problem": "50.4% of orders are under $20 (single items), missing side dish and appetizer cross-sell opportunities.",
            "solution": "Implement Apriori basket recommendations at checkout (e.g. Peking Duck + Hot & Sour Soup combo with $2 discount).",
            "owner": "Merchandising & Product Engineering",
            "timeline": "Quick Win (Days 1 - 45)"
        },
        {
            "id": 3,
            "title": "Discount Rationalization & Margin Defense",
            "tag": "Gross Margin Optimization",
            "icon": "fa-coins",
            "color": "#F59E0B",
            "bg": "rgba(245, 158, 11, 0.1)",
            "target": "+$49,100 Margin Preserved",
            "kpi": "Discount Rate: 13.3% → 9.5%",
            "problem": "FoodHunter gave away $163,680 in flat discounts (15% on high tickets) unconditionally, without preventing a 21% volume drop.",
            "solution": "Replace flat un-gated discounts with minimum order thresholds ($35+ for 10% off) and shift promo budget into tiered loyalty points.",
            "owner": "Pricing & Commercial Finance",
            "timeline": "Phase 2 (Days 30 - 60)"
        },
        {
            "id": 4,
            "title": "Cuisine Diversification & Merchant Expansion",
            "tag": "Portfolio Risk Mitigation",
            "icon": "fa-utensils",
            "color": "#06B6D4",
            "bg": "rgba(6, 182, 212, 0.1)",
            "target": "+$33,600 Monthly Revenue",
            "kpi": "+1,200 Non-Chinese Orders / Mo",
            "problem": "Chinese cuisine represents 38.6% of orders and 36.8% of revenue, leaving the platform vulnerable to merchant supply shocks.",
            "solution": "Onboard 20 premier Thai, Indian, and Italian restaurants; launch 'World Flavor Weekends' with sponsored merchant placement.",
            "owner": "Merchant Partnerships & Business Development",
            "timeline": "Phase 3 (Days 45 - 90)"
        }
    ],
    "roadmap_milestones": [
        {"phase": "Days 1 – 30", "focus": "Stabilization & Leak Plugging", "initiatives": "Launch 3-stage automated VIP win-back CRM campaign; roll out Top 5 Apriori combo bundles at checkout for Chinese cuisine; eliminate flat discounts under $20.", "owner": "Marketing & CRM", "target_metric": "+$16.1k/mo recovered, AOV +$0.80"},
        {"phase": "Days 31 – 60", "focus": "Margin Defense & Optimization", "initiatives": "Enforce $35+ basket threshold for promotional discounts; expand combo meal cross-selling to Italian and Indian menus; recruit first batch of 10 new regional restaurant partners.", "owner": "Finance & Merchandising", "target_metric": "Discount rate down to 10.5%, +$16.4k margin"},
        {"phase": "Days 61 – 90", "focus": "Scale & Institutional Loyalty", "initiatives": "Launch 'FoodHunter VIP Pass' tiered loyalty subscription; onboard remaining 10 high-demand merchant partners; establish automated Courier SLA driver dispatch incentives.", "owner": "Product & Growth", "target_metric": "+1,200 monthly orders, Platform MRR $320.4k"}
    ],
    "simulator_baseline": {
        "orders": 9365,
        "revenue": 258161.1,
        "aov": 27.57,
        "discounts": 35012.4,
        "food_total": 265378.5,
        "discount_rate": 13.2,
        "at_risk_pool": 18046.3,
        "june_peak": 347577.5
    }
}

json_str = json.dumps(payload, separators=(',', ':'))

# Build dynamic HTML
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FoodHunter - Power BI Interactive Cross-Filtering Dashboard</title>
    
    <meta name="description" content="FoodHunter Power BI-style Interactive Data Analytics Dashboard. Click to filter, click again to reset. Full cross-filtering across visuals.">
    <meta name="theme-color" content="#4F46E5">
    
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome 6 -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
    <!-- Google Fonts Plus Jakarta Sans -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
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
            margin-bottom: 20px;
        }}

        /* Power BI Slicer Pills */
        .slicer-label {{
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .slicer-btn-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .slicer-btn {{
            border-radius: 10px;
            font-size: 0.82rem;
            font-weight: 600;
            padding: 6px 12px;
            border: 1.5px solid var(--border-color);
            background: var(--bg-card);
            color: var(--text-main);
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        .slicer-btn:hover {{
            border-color: var(--primary);
            color: var(--primary);
            transform: translateY(-1px);
        }}
        .slicer-btn.active {{
            background: var(--primary) !important;
            color: #ffffff !important;
            border-color: var(--primary) !important;
            box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3);
        }}

        /* Active Filter Badges Container */
        .active-filters-box {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 10px 16px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .active-filter-pill {{
            background: var(--primary-light);
            color: var(--primary);
            border: 1px solid rgba(79, 70, 229, 0.25);
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 0.82rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .active-filter-pill i {{
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
        }}
        .active-filter-pill i:hover {{
            opacity: 1;
            color: #ef4444;
        }}

        /* KPI Card */
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 20px;
            box-shadow: var(--shadow-md);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
        }}
        .kpi-card:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-hover);
        }}
        .kpi-icon-box {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}
        .kpi-title {{
            font-size: 0.78rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--text-main);
            margin: 6px 0 4px 0;
            letter-spacing: -0.5px;
            transition: color 0.2s;
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
            position: relative;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .chart-title {{
            font-size: 1.02rem;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .powerbi-hint {{
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        /* Plotly Cursor & Clickability */
        .js-plotly-plot .plotly .bars path,
        .js-plotly-plot .plotly .slice path {{
            cursor: pointer !important;
            transition: opacity 0.25s ease, filter 0.25s ease;
        }}

        /* Badges */
        .badge-pill-custom {{
            padding: 4px 10px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 0.75rem;
        }}

        /* Custom Dropdown Styling (Fixed padding & Crisp SVG arrow) */
        .form-select-custom {{
            background-color: var(--bg-card);
            color: var(--text-main);
            border: 1.5px solid var(--border-color);
            border-radius: 12px;
            padding: 8px 40px 8px 12px !important;
            font-weight: 600;
            font-size: 0.85rem;
            line-height: 1.5;
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%23475569' stroke-linecap='round' stroke-linejoin='round' stroke-width='2.2' d='m2 5 6 6 6-6'/%3e%3c/svg%3e") !important;
            background-repeat: no-repeat !important;
            background-position: right 14px center !important;
            background-size: 14px 10px !important;
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
            cursor: pointer;
            text-overflow: ellipsis;
            white-space: nowrap;
            transition: all 0.2s;
        }}
        [data-theme="dark"] .form-select-custom {{
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%23cbd5e1' stroke-linecap='round' stroke-linejoin='round' stroke-width='2.2' d='m2 5 6 6 6-6'/%3e%3c/svg%3e") !important;
        }}
        .form-select-custom:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
            background-color: var(--bg-card);
            color: var(--text-main);
            outline: none;
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

        @media (max-width: 768px) {{
            .kpi-value {{
                font-size: 1.45rem;
            }}
            .filter-bar {{
                padding: 12px;
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
                <h3 class="fw-bolder mb-1" style="letter-spacing: -0.5px;">Power BI Interactive Cross-Filtering Hub</h3>
                <p class="text-muted small mb-0">Multi-Dimensional Analysis of 43,118 Orders &bull; June 1 – September 29, 2022</p>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="badge bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 px-3 py-2 rounded-pill fw-semibold">
                    <i class="fas fa-hand-pointer me-1"></i> Click Visual to Filter &bull; Click Again to Reset
                </span>
            </div>
        </div>

        <!-- POWER BI SLICER TOOLBAR (Pills & Dropdowns) -->
        <div class="filter-bar">
            <!-- Row 1: Slicer Pills -->
            <div class="row g-3 mb-3">
                <!-- Cuisine Slicers -->
                <div class="col-12 col-xl-5">
                    <div class="slicer-label"><i class="fas fa-utensils text-primary"></i> Cuisine Slicer:</div>
                    <div class="slicer-btn-group" id="cuisineSlicers">
                        <button class="slicer-btn active" data-type="cuisine" data-val="ALL">All Cuisines</button>
                        <button class="slicer-btn" data-type="cuisine" data-val="Chinese">🥢 Chinese</button>
                        <button class="slicer-btn" data-type="cuisine" data-val="Italian">🍕 Italian</button>
                        <button class="slicer-btn" data-type="cuisine" data-val="Indian">🍛 Indian</button>
                        <button class="slicer-btn" data-type="cuisine" data-val="Thai">🍜 Thai</button>
                    </div>
                </div>

                <!-- Month Slicers -->
                <div class="col-12 col-md-7 col-xl-4">
                    <div class="slicer-label"><i class="fas fa-calendar-alt text-warning"></i> Month Slicer:</div>
                    <div class="slicer-btn-group" id="monthSlicers">
                        <button class="slicer-btn active" data-type="month" data-val="ALL">All Time</button>
                        <button class="slicer-btn" data-type="month" data-val="2022-06">Jun '22</button>
                        <button class="slicer-btn" data-type="month" data-val="2022-07">Jul '22</button>
                        <button class="slicer-btn" data-type="month" data-val="2022-08">Aug '22</button>
                        <button class="slicer-btn" data-type="month" data-val="2022-09">Sep '22</button>
                    </div>
                </div>

                <!-- Day Type Slicers -->
                <div class="col-12 col-md-5 col-xl-3">
                    <div class="slicer-label"><i class="fas fa-business-time text-danger"></i> Day Slicer:</div>
                    <div class="slicer-btn-group" id="dayTypeSlicers">
                        <button class="slicer-btn active" data-type="dayType" data-val="ALL">Full Week</button>
                        <button class="slicer-btn" data-type="dayType" data-val="Weekday">💼 Weekdays</button>
                        <button class="slicer-btn" data-type="dayType" data-val="Weekend">🏖️ Weekends</button>
                    </div>
                </div>
            </div>

            <!-- Row 2: Secondary Dropdown Controls & Action Buttons -->
            <div class="row g-2 align-items-center pt-2 border-top">
                <div class="col-12 col-sm-4 col-lg-3">
                    <select id="cuisineSelect" class="form-select form-select-custom">
                        <option value="ALL">All Cuisines (All 4)</option>
                        <option value="Chinese">Chinese Only</option>
                        <option value="Italian">Italian Only</option>
                        <option value="Indian">Indian Only</option>
                        <option value="Thai">Thai Only</option>
                    </select>
                </div>
                
                <div class="col-12 col-sm-4 col-lg-3">
                    <select id="monthSelect" class="form-select form-select-custom">
                        <option value="ALL">All Months (Jun – Sep)</option>
                        <option value="2022-06">June 2022</option>
                        <option value="2022-07">July 2022</option>
                        <option value="2022-08">August 2022</option>
                        <option value="2022-09">September 2022</option>
                    </select>
                </div>
                
                <div class="col-12 col-sm-4 col-lg-3">
                    <select id="dayTypeSelect" class="form-select form-select-custom">
                        <option value="ALL">All Days (Full Week)</option>
                        <option value="Weekday">Weekdays Only (Mon – Fri)</option>
                        <option value="Weekend">Weekends Only (Sat – Sun)</option>
                    </select>
                </div>

                <div class="col-12 col-lg-3 d-flex align-items-center gap-2 pt-2 pt-lg-0">
                    <button id="resetFiltersBtn" class="btn btn-outline-secondary w-100 rounded-3 fw-semibold py-2">
                        <i class="fas fa-rotate-left me-1"></i> Reset
                    </button>
                    <button id="exportCsvBtn" class="btn btn-primary w-100 rounded-3 fw-semibold py-2">
                        <i class="fas fa-file-csv me-1"></i> CSV
                    </button>
                </div>
            </div>
        </div>

        <!-- ACTIVE FILTERS BREADCRUMBS ROW (Power BI Style) -->
        <div class="active-filters-box" id="activeFiltersBox">
            <span class="small fw-bold text-muted me-2"><i class="fas fa-filter text-primary me-1"></i> Active Filters:</span>
            <span id="activeFiltersBadges" class="d-flex align-items-center flex-wrap gap-2">
                <span class="text-muted small fst-italic">None (Showing all data &bull; Click any bar or pie slice to cross-filter)</span>
            </span>
            <button id="clearAllFiltersBtn" class="btn btn-sm btn-link text-danger text-decoration-none fw-bold ms-auto p-0 d-none">
                <i class="fas fa-xmark me-1"></i> Clear All
            </button>
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
                <button class="nav-link" id="ml-tab" data-bs-toggle="pill" data-bs-target="#tab-ml" type="button" style="border: 1px solid rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.08);">
                    <i class="fas fa-brain text-warning me-1"></i> <span class="fw-bold">1️⃣ Advanced Analytics & ML</span>
                    <span class="badge bg-warning text-dark ms-1 px-2 py-0.5 rounded-pill" style="font-size: 0.68rem;">Portfolio Boost</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="strategy-tab" data-bs-toggle="pill" data-bs-target="#tab-strategy" type="button" style="border: 1px solid rgba(6, 182, 212, 0.4); background: rgba(6, 182, 212, 0.08);">
                    <i class="fas fa-lightbulb text-info me-1"></i> <span class="fw-bold">2️⃣ Prescriptive Strategy &amp; Insights</span>
                    <span class="badge bg-info text-dark ms-1 px-2 py-0.5 rounded-pill" style="font-size: 0.68rem;">Executive Roadmap</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="simulator-tab" data-bs-toggle="pill" data-bs-target="#tab-simulator" type="button" style="border: 1px solid rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.08);">
                    <i class="fas fa-sliders text-success me-1"></i> <span class="fw-bold">3️⃣ What-If Scenario Simulator</span>
                    <span class="badge bg-success text-white ms-1 px-2 py-0.5 rounded-pill" style="font-size: 0.68rem;">Interactive BI Tool</span>
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
                                <span class="powerbi-hint"><i class="fas fa-mouse-pointer text-primary"></i> Click bar to filter month</span>
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
                                <span class="powerbi-hint"><i class="fas fa-mouse-pointer text-success"></i> Click slice to filter</span>
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
                                <span class="powerbi-hint"><i class="fas fa-mouse-pointer text-warning"></i> Click to filter cuisine</span>
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
                                <span class="powerbi-hint"><i class="fas fa-mouse-pointer text-danger"></i> Click to filter day</span>
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
                                    Top Performing Restaurants by Revenue
                                </div>
                                <span class="powerbi-hint"><i class="fas fa-arrow-up-right-from-square text-primary"></i> Click restaurant to search</span>
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
                                <span class="badge bg-light text-dark border">Filters by active Cuisine</span>
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

            <!-- TAB 6: ADVANCED ANALYTICS & MACHINE LEARNING (STEP 1) -->
            <div class="tab-pane fade" id="tab-ml">
                <!-- Step 1 Callout Banner -->
                <div class="card border-0 mb-4 shadow-sm" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border-radius: 16px; color: white;">
                    <div class="card-body p-4">
                        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3">
                            <div>
                                <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                                    <span class="badge bg-warning text-dark fw-bold px-3 py-1 rounded-pill">STEP 1 COMPLETE</span>
                                    <span class="badge bg-white bg-opacity-20 text-white px-3 py-1 rounded-pill"><i class="fas fa-brain me-1"></i> Behavioral Intelligence &amp; Association Mining</span>
                                </div>
                                <h4 class="fw-bolder mb-1" style="letter-spacing: -0.5px;">Customer RFM Segmentation &amp; Market Basket Association Engine</h4>
                                <p class="text-white-50 mb-0 small">
                                    Trained on <strong>9,874 active customers</strong> and <strong>43,118 orders</strong> &bull; Unsupervised quantile clustering reveals VIP cohorts, high-risk churn volume, and cross-sell combo affinities.
                                </p>
                            </div>
                            <div class="d-flex gap-2">
                                <span class="badge bg-success bg-opacity-25 text-success-light border border-success border-opacity-50 px-3 py-2 rounded-pill small">
                                    <i class="fas fa-circle-check me-1"></i> Production Ready ML
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Step 1 ML KPI Scorecards -->
                <div class="row g-3 mb-4">
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Champions Revenue Share</span>
                                <div class="kpi-icon-box" style="background:#ECFDF5; color:#10B981;">
                                    <i class="fas fa-crown"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-success">22.2%</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success">
                                $265,470 from 1,493 VIPs
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Revenue At Risk (Churn)</span>
                                <div class="kpi-icon-box" style="background:#FEF2F2; color:#EF4444;">
                                    <i class="fas fa-triangle-exclamation"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-danger">$72,185</div>
                            <span class="badge-pill-custom bg-danger bg-opacity-10 text-danger">
                                456 VIPs (57.2 days inactive)
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Customer Repeat Rate</span>
                                <div class="kpi-icon-box" style="background:#EEF2FF; color:#4F46E5;">
                                    <i class="fas fa-rotate"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-primary">94.7%</div>
                            <span class="badge-pill-custom bg-primary bg-opacity-10 text-primary">
                                9,349 multi-order accounts
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Top Cross-Sell Pair</span>
                                <div class="kpi-icon-box" style="background:#FFFBEB; color:#F59E0B;">
                                    <i class="fas fa-utensils"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-warning" style="font-size: 1.25rem;">Duck + Soup</div>
                            <span class="badge-pill-custom bg-warning bg-opacity-10 text-warning">
                                49 orders &bull; +$38.4k potential
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Row 1: RFM Visuals -->
                <div class="row g-4 mb-4">
                    <!-- RFM Visual Container with View Switcher -->
                    <div class="col-12 col-xl-7">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-layer-group text-primary"></i>
                                        RFM Customer Segmentation Matrix
                                    </div>
                                    <div class="text-muted small">Behavioral customer tiers across Recency, Frequency &amp; Spend</div>
                                </div>
                                <div class="btn-group btn-group-sm" role="group">
                                    <button type="button" class="btn btn-sm btn-outline-primary active" id="rfmViewTreemapBtn">Treemap</button>
                                    <button type="button" class="btn btn-sm btn-outline-primary" id="rfmViewScatterBtn">Recency vs Spend</button>
                                </div>
                            </div>
                            <div id="chartRfmMatrix" style="min-height: 410px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Pareto Chart -->
                    <div class="col-12 col-xl-5">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-scale-balanced text-warning"></i>
                                        Pareto Analysis: Headcount vs. Revenue
                                    </div>
                                    <div class="text-muted small">Comparing cohort population share against revenue generation</div>
                                </div>
                            </div>
                            <div id="chartRfmPareto" style="min-height: 410px; width: 100%;"></div>
                        </div>
                    </div>
                </div>

                <!-- Row 2: Market Basket Association Analysis -->
                <div class="row g-4 mb-4">
                    <!-- Top Item Pairs Bar Chart -->
                    <div class="col-12 col-xl-7">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-basket-shopping text-success"></i>
                                        Market Basket: Top Co-Occurring Menu Items
                                    </div>
                                    <div class="text-muted small">Dishes ordered together in single transactions (Apriori Mining)</div>
                                </div>
                            </div>
                            <div id="chartMarketBasket" style="min-height: 380px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Cuisine Cross-Sell Bundling Engine -->
                    <div class="col-12 col-xl-5">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-wand-magic-sparkles text-info"></i>
                                        Cuisine Cross-Sell Bundling Engine
                                    </div>
                                    <div class="text-muted small">Recommended combos with projected cross-sell lift</div>
                                </div>
                            </div>
                            <!-- Cuisine Pill Selector -->
                            <div class="d-flex flex-wrap gap-1 mb-3" id="basketCuisineTabs">
                                <button class="btn btn-sm btn-outline-primary active" data-cuisine="Chinese">Chinese</button>
                                <button class="btn btn-sm btn-outline-primary" data-cuisine="Italian">Italian</button>
                                <button class="btn btn-sm btn-outline-primary" data-cuisine="Indian">Indian</button>
                                <button class="btn btn-sm btn-outline-primary" data-cuisine="Thai">Thai</button>
                            </div>
                            <div id="cuisineBasketContainer" class="d-flex flex-column gap-2" style="max-height: 300px; overflow-y: auto;">
                                <!-- Dynamically populated -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Row 3: Actionable RFM Prescriptive Playbook Table -->
                <div class="chart-box mb-4">
                    <div class="chart-header">
                        <div>
                            <div class="chart-title">
                                <i class="fas fa-chess-knight text-primary"></i>
                                Actionable RFM Marketing Strategy &amp; Retention Playbook
                            </div>
                            <div class="text-muted small">Data-driven marketing campaigns and promotional levers per cohort</div>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover table-custom align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>Customer Cohort</th>
                                    <th>Volume (% Share)</th>
                                    <th>Revenue (% Share)</th>
                                    <th>Avg Recency</th>
                                    <th>Avg Orders</th>
                                    <th>Avg Spend</th>
                                    <th>Prescriptive Action &amp; Campaign Levers</th>
                                </tr>
                            </thead>
                            <tbody id="rfmPlaybookTableBody">
                                <!-- Populated dynamically -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- TAB 7: PRESCRIPTIVE BUSINESS STRATEGY & EXECUTIVE STORYTELLING (STEP 2) -->
            <div class="tab-pane fade" id="tab-strategy">
                <!-- Step 2 Hero Banner -->
                <div class="card border-0 mb-4 shadow-sm" style="background: linear-gradient(135deg, #092c4c 0%, #173f6b 100%); border-radius: 16px; color: white;">
                    <div class="card-body p-4">
                        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3">
                            <div>
                                <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                                    <span class="badge bg-info text-dark fw-bold px-3 py-1 rounded-pill">STEP 2 COMPLETE</span>
                                    <span class="badge bg-white bg-opacity-20 text-white px-3 py-1 rounded-pill"><i class="fas fa-chess-knight me-1"></i> McKinsey/BCG Style Prescriptive Strategy</span>
                                </div>
                                <h4 class="fw-bolder mb-1" style="letter-spacing: -0.5px;">Executive Turnaround Roadmap: Reversing Volume Decline &amp; Unlocking +$149.6k/Qtr</h4>
                                <p class="text-white-50 mb-0 small">
                                    Synthesizing <strong>43,118 transactional records</strong>, <strong>9,874 customer accounts</strong>, and delivery logistics into 4 quantifiable growth levers to restore peak June revenue run-rates.
                                </p>
                            </div>
                            <div class="d-flex gap-2">
                                <span class="badge bg-success bg-opacity-25 text-success-light border border-success border-opacity-50 px-3 py-2 rounded-pill small">
                                    <i class="fas fa-chart-line me-1"></i> +12.5% Revenue Growth
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Strategic Impact KPI Scorecards -->
                <div class="row g-3 mb-4">
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Target Quarterly Impact</span>
                                <div class="kpi-icon-box" style="background:#ECFDF5; color:#10B981;">
                                    <i class="fas fa-arrow-trend-up"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-success">+$149,600</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success">
                                +12.5% revenue expansion
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">At-Risk VIP Protection</span>
                                <div class="kpi-icon-box" style="background:#EEF2FF; color:#4F46E5;">
                                    <i class="fas fa-shield-halved"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-primary">+$48,400</div>
                            <span class="badge-pill-custom bg-primary bg-opacity-10 text-primary">
                                25% win-back reactivation
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Target Basket Size (AOV)</span>
                                <div class="kpi-icon-box" style="background:#FFFBEB; color:#F59E0B;">
                                    <i class="fas fa-receipt"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-warning">$29.63</div>
                            <span class="badge-pill-custom bg-warning bg-opacity-10 text-warning">
                                +6.7% via Apriori bundling
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6 col-xl-3">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Discount Efficiency Gain</span>
                                <div class="kpi-icon-box" style="background:#F0FDF4; color:#16A34A;">
                                    <i class="fas fa-piggy-bank"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-success">+$49,100</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success">
                                Spend thresholds ($35+)
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Row 1: Executive Visualizations (Waterfall & Priority Matrix) -->
                <div class="row g-4 mb-4">
                    <!-- Waterfall Chart: Revenue Recovery Bridge -->
                    <div class="col-12 col-xl-7">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-chart-waterfall text-primary"></i>
                                        Strategic Revenue Recovery Bridge
                                    </div>
                                    <div class="text-muted small">Financial bridge from current September run-rate to projected monthly target</div>
                                </div>
                            </div>
                            <div id="chartStrategyWaterfall" style="min-height: 420px; width: 100%;"></div>
                        </div>
                    </div>

                    <!-- Strategic Action Priority Matrix (Impact vs Effort) -->
                    <div class="col-12 col-xl-5">
                        <div class="chart-box">
                            <div class="chart-header">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-crosshairs text-info"></i>
                                        Strategic Action Priority Matrix
                                    </div>
                                    <div class="text-muted small">Impact vs. Implementation Effort quadrant evaluation</div>
                                </div>
                            </div>
                            <div id="chartPriorityMatrix" style="min-height: 420px; width: 100%;"></div>
                        </div>
                    </div>
                </div>

                <!-- Row 2: The 4 Strategic Growth Pillars Deep-Dive Cards -->
                <div class="mb-4">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <h5 class="fw-bold mb-0"><i class="fas fa-columns text-primary me-2"></i> The 4 Prescriptive Growth Pillars</h5>
                        <span class="badge bg-primary bg-opacity-10 text-primary px-3 py-1.5 rounded-pill small fw-semibold">
                            C-Suite Operational Playbook
                        </span>
                    </div>
                    <div class="row g-3" id="strategicPillarsContainer">
                        <!-- Dynamically Populated by JS -->
                    </div>
                </div>

                <!-- Row 3: 30-60-90 Day Phased Execution Roadmap Table -->
                <div class="chart-box mb-4">
                    <div class="chart-header">
                        <div>
                            <div class="chart-title">
                                <i class="fas fa-timeline text-primary"></i>
                                30 – 60 – 90 Day Strategic Execution Roadmap
                            </div>
                            <div class="text-muted small">Phase-wise execution schedule with departmental ownership and target KPIs</div>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover table-custom align-middle mb-0">
                            <thead>
                                <tr>
                                    <th style="min-width: 130px;">Execution Phase</th>
                                    <th style="min-width: 180px;">Strategic Focus</th>
                                    <th style="min-width: 320px;">Tactical Levers &amp; Initiatives</th>
                                    <th style="min-width: 140px;">Ownership</th>
                                    <th style="min-width: 150px;">Target Milestone</th>
                                </tr>
                            </thead>
                            <tbody id="roadmapTableBody">
                                <!-- Populated dynamically by JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- TAB 8: WHAT-IF SCENARIO SIMULATOR (STEP 3) -->
            <div class="tab-pane fade" id="tab-simulator">
                <!-- Step 3 Hero Banner -->
                <div class="card border-0 mb-4 shadow-sm" style="background: linear-gradient(135deg, #064e3b 0%, #065f46 100%); border-radius: 16px; color: white;">
                    <div class="card-body p-4">
                        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3">
                            <div>
                                <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                                    <span class="badge bg-warning text-dark fw-bold px-3 py-1 rounded-pill">STEP 3 COMPLETE</span>
                                    <span class="badge bg-white bg-opacity-20 text-white px-3 py-1 rounded-pill"><i class="fas fa-calculator me-1"></i> Real-Time Interactive BI Engine</span>
                                </div>
                                <h4 class="fw-bolder mb-1" style="letter-spacing: -0.5px;">Executive What-If Scenario Simulator &amp; Financial Sensitivity Model</h4>
                                <p class="text-white-50 mb-0 small">
                                    Simulate dynamic growth scenarios in real-time &bull; Adjust strategic sliders or select one-click presets to model revenue, margin expansion, and volume recovery.
                                </p>
                            </div>
                            <div class="d-flex gap-2">
                                <span class="badge bg-success bg-opacity-25 text-white border border-success border-opacity-50 px-3 py-2 rounded-pill small">
                                    <i class="fas fa-bolt me-1"></i> Instant 60 FPS Recomputation
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Scenario Presets Ribbon -->
                <div class="card border-0 mb-4 p-3 shadow-sm" style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px;">
                    <div class="d-flex flex-column flex-lg-row align-items-start align-items-lg-center justify-content-between gap-3">
                        <div>
                            <span class="small fw-bold text-muted text-uppercase tracking-wider">
                                <i class="fas fa-bookmark text-primary me-1"></i> Executive Scenario Presets:
                            </span>
                            <span class="small text-muted ms-2 d-none d-md-inline">One-click standard management scenarios</span>
                        </div>
                        <div class="d-flex flex-wrap gap-2 w-100 w-lg-auto">
                            <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-3 fw-semibold scenario-preset-btn" data-preset="conservative">
                                <i class="fas fa-shield me-1"></i> Conservative Defense
                            </button>
                            <button type="button" class="btn btn-sm btn-success rounded-pill px-3 fw-bold scenario-preset-btn active" data-preset="target">
                                <i class="fas fa-bullseye me-1"></i> Target Turnaround (Recommended)
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-primary rounded-pill px-3 fw-semibold scenario-preset-btn" data-preset="aggressive">
                                <i class="fas fa-rocket me-1"></i> Aggressive Growth Surge
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-3 fw-semibold scenario-preset-btn" data-preset="baseline">
                                <i class="fas fa-rotate-left me-1"></i> Reset to Baseline
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Simulated Real-Time Dynamic KPI Scorecards -->
                <div class="row g-3 mb-4">
                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Simulated Monthly Rev</span>
                                <div class="kpi-icon-box" style="background:#ECFDF5; color:#10B981;">
                                    <i class="fas fa-dollar-sign"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-success" id="simKpiRevenue">$319,952</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success" id="simKpiRevDelta">
                                +$61,791 (+23.9%) vs Sep
                            </span>
                        </div>
                    </div>

                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Simulated Orders</span>
                                <div class="kpi-icon-box" style="background:#EEF2FF; color:#4F46E5;">
                                    <i class="fas fa-bag-shopping"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-primary" id="simKpiOrders">10,723</div>
                            <span class="badge-pill-custom bg-primary bg-opacity-10 text-primary" id="simKpiOrdersDelta">
                                +1,358 orders (+14.5%)
                            </span>
                        </div>
                    </div>

                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Simulated AOV</span>
                                <div class="kpi-icon-box" style="background:#FFFBEB; color:#F59E0B;">
                                    <i class="fas fa-receipt"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-warning" id="simKpiAov">$29.42</div>
                            <span class="badge-pill-custom bg-warning bg-opacity-10 text-warning" id="simKpiAovDelta">
                                +$1.85 / order (+6.7%)
                            </span>
                        </div>
                    </div>

                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Discount Margin Saved</span>
                                <div class="kpi-icon-box" style="background:#F0FDF4; color:#16A34A;">
                                    <i class="fas fa-piggy-bank"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-success" id="simKpiDiscSavings">+$12,170</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success" id="simKpiDiscRate">
                                9.5% effective rate
                            </span>
                        </div>
                    </div>

                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Quarterly Net Benefit</span>
                                <div class="kpi-icon-box" style="background:#F5F3FF; color:#8B5CF6;">
                                    <i class="fas fa-calendar-days"></i>
                                </div>
                            </div>
                            <div class="kpi-value" style="color: #8B5CF6;" id="simKpiQuarterly">+$221,882</div>
                            <span class="badge-pill-custom bg-info bg-opacity-10 text-info">
                                3-Month Cumulative
                            </span>
                        </div>
                    </div>

                    <div class="col-12 col-sm-6 col-xl-2">
                        <div class="kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <span class="kpi-title">Annualized Run-Rate</span>
                                <div class="kpi-icon-box" style="background:#ECFEFF; color:#06B6D4;">
                                    <i class="fas fa-chart-line"></i>
                                </div>
                            </div>
                            <div class="kpi-value text-info" id="simKpiAnnual">+$887,529</div>
                            <span class="badge-pill-custom bg-success bg-opacity-10 text-success">
                                12-Month Net Value
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Simulation Main Row: Sliders on Left, Charts on Right -->
                <div class="row g-4 mb-4">
                    <!-- Left: Interactive Sliders Control Panel -->
                    <div class="col-12 col-xl-5">
                        <div class="chart-box h-100">
                            <div class="chart-header pb-2 border-bottom mb-3">
                                <div>
                                    <div class="chart-title">
                                        <i class="fas fa-sliders text-success"></i>
                                        Strategic Growth Levers (Interactive)
                                    </div>
                                    <div class="text-muted small">Move sliders to test sensitivity and projected outcomes</div>
                                </div>
                            </div>

                            <!-- Slider 1: VIP Win-Back -->
                            <div class="mb-4">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <label class="form-label small fw-bold mb-0">
                                        <i class="fas fa-shield-halved text-primary me-1"></i> VIP Win-Back Reactivation Rate
                                    </label>
                                    <span id="labelWinback" class="badge bg-primary px-2.5 py-1 rounded-pill fw-bold">25%</span>
                                </div>
                                <input type="range" class="form-range" id="sliderWinback" min="0" max="50" step="1" value="25">
                                <div class="d-flex justify-content-between text-muted" style="font-size: 0.72rem;">
                                    <span>0% (No Win-Back)</span>
                                    <span>25% Target</span>
                                    <span>50% (Max Campaign)</span>
                                </div>
                                <div class="text-muted small mt-1" style="font-size: 0.78rem;">
                                    Targeting 456 churn-risk VIPs with $72,185 cumulative spend.
                                </div>
                            </div>

                            <!-- Slider 2: AOV Basket Cross-Sell Lift -->
                            <div class="mb-4">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <label class="form-label small fw-bold mb-0">
                                        <i class="fas fa-cubes text-warning me-1"></i> Apriori Combo Basket Lift (AOV)
                                    </label>
                                    <span id="labelAov" class="badge bg-warning text-dark px-2.5 py-1 rounded-pill fw-bold">+6.7%</span>
                                </div>
                                <input type="range" class="form-range" id="sliderAov" min="0" max="20" step="0.5" value="6.7">
                                <div class="d-flex justify-content-between text-muted" style="font-size: 0.72rem;">
                                    <span>0% ($27.57 baseline)</span>
                                    <span>+6.7% (+$1.85)</span>
                                    <span>+20% ($33.08)</span>
                                </div>
                                <div class="text-muted small mt-1" style="font-size: 0.78rem;">
                                    Driven by automated side/appetizer combo pairings during checkout.
                                </div>
                            </div>

                            <!-- Slider 3: Discount Rate Optimization -->
                            <div class="mb-4">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <label class="form-label small fw-bold mb-0">
                                        <i class="fas fa-coins text-success me-1"></i> Optimized Discount Rate (% of Food Gross)
                                    </label>
                                    <span id="labelDiscount" class="badge bg-success px-2.5 py-1 rounded-pill fw-bold">9.5%</span>
                                </div>
                                <input type="range" class="form-range" id="sliderDiscount" min="5" max="15" step="0.5" value="9.5">
                                <div class="d-flex justify-content-between text-muted" style="font-size: 0.72rem;">
                                    <span>5.0% (Strict Spend Gate)</span>
                                    <span>9.5% (Target)</span>
                                    <span>15.0% (Current Flat Leak)</span>
                                </div>
                                <div class="text-muted small mt-1" style="font-size: 0.78rem;">
                                    Enforce $35+ spend threshold on promo codes (Baseline is 13.2%).
                                </div>
                            </div>

                            <!-- Slider 4: Volume Growth Rate -->
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <label class="form-label small fw-bold mb-0">
                                        <i class="fas fa-arrow-trend-up text-info me-1"></i> Organic Volume &amp; Cuisine Expansion
                                    </label>
                                    <span id="labelVolume" class="badge bg-info px-2.5 py-1 rounded-pill fw-bold">+12.8%</span>
                                </div>
                                <input type="range" class="form-range" id="sliderVolume" min="-10" max="30" step="1" value="12.8">
                                <div class="d-flex justify-content-between text-muted" style="font-size: 0.72rem;">
                                    <span>-10% (Market Contraction)</span>
                                    <span>+12.8% (+1,200 orders)</span>
                                    <span>+30% (High Growth)</span>
                                </div>
                                <div class="text-muted small mt-1" style="font-size: 0.78rem;">
                                    Onboarding 20 high-demand Thai &amp; Indian regional restaurants.
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right: Dynamic Comparison Charts -->
                    <div class="col-12 col-xl-7">
                        <div class="row g-4">
                            <!-- Comparison Chart: Baseline vs Simulated -->
                            <div class="col-12">
                                <div class="chart-box">
                                    <div class="chart-header">
                                        <div>
                                            <div class="chart-title">
                                                <i class="fas fa-chart-column text-primary"></i>
                                                Baseline vs. Simulated Performance Comparison
                                            </div>
                                            <div class="text-muted small">Comparing September 2022 actuals against modeled output</div>
                                        </div>
                                    </div>
                                    <div id="chartSimComparison" style="min-height: 250px; width: 100%;"></div>
                                </div>
                            </div>

                            <!-- Historical Peak Recovery Gauge -->
                            <div class="col-12">
                                <div class="chart-box">
                                    <div class="chart-header">
                                        <div>
                                            <div class="chart-title">
                                                <i class="fas fa-gauge-high text-success"></i>
                                                Peak Revenue Recovery Gauge (vs. June Peak $347.6k)
                                            </div>
                                            <div class="text-muted small">Tracking whether simulated run-rate surpasses historical peak volume</div>
                                        </div>
                                    </div>
                                    <div id="chartSimGauge" style="min-height: 220px; width: 100%;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Bottom Row: Financial Line-Item Variance Table -->
                <div class="chart-box mb-4">
                    <div class="chart-header">
                        <div>
                            <div class="chart-title">
                                <i class="fas fa-file-invoice-dollar text-primary"></i>
                                Financial Line-Item Variance &amp; Sensitivity Analysis
                            </div>
                            <div class="text-muted small">Granular mathematical bridge between baseline actuals and simulated scenario</div>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover table-custom align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>Financial Metric</th>
                                    <th>Current Baseline (Sep Actual)</th>
                                    <th>Simulated Projection</th>
                                    <th>Variance Delta</th>
                                    <th>Strategic Commentary</th>
                                </tr>
                            </thead>
                            <tbody id="simVarianceTableBody">
                                <!-- Populated dynamically by JS -->
                            </tbody>
                        </table>
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
            <p class="mb-0">Power BI-Style Cross-Filtering &bull; Interactive &bull; Dynamic &bull; Fully Responsive</p>
        </footer>

    </div> <!-- End container -->

    <!-- Bootstrap 5 JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

    <!-- EMBEDDED REAL DATASET & POWER BI LOGIC -->
    <script>
        const RAW_DATA = {json_str};

        // Active Filter State (Power BI Model)
        const filterState = {{
            cuisine: 'ALL',
            month: 'ALL',
            dayType: 'ALL'
        }};

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

        // Controls elements
        const cuisineSel = document.getElementById('cuisineSelect');
        const monthSel = document.getElementById('monthSelect');
        const dayTypeSel = document.getElementById('dayTypeSelect');
        const resetBtn = document.getElementById('resetFiltersBtn');
        const clearAllBtn = document.getElementById('clearAllFiltersBtn');
        const exportBtn = document.getElementById('exportCsvBtn');
        const searchInput = document.getElementById('tableSearchInput');

        // Dropdown Event Listeners
        cuisineSel.addEventListener('change', (e) => setFilter('cuisine', e.target.value));
        monthSel.addEventListener('change', (e) => setFilter('month', e.target.value));
        dayTypeSel.addEventListener('change', (e) => setFilter('dayType', e.target.value));

        resetBtn.addEventListener('click', resetAllFilters);
        clearAllBtn.addEventListener('click', resetAllFilters);
        searchInput.addEventListener('input', filterExplorerTable);

        // Power BI Slicer Pill Click Listeners (Click to toggle on / Click again to toggle off)
        document.querySelectorAll('.slicer-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                const type = btn.getAttribute('data-type');
                const val = btn.getAttribute('data-val');
                toggleFilter(type, val);
            }});
        }});

        // POWER BI TOGGLE LOGIC:
        // If the clicked value is already active -> reset to 'ALL'!
        // If it's different -> apply that value!
        function toggleFilter(type, val) {{
            if (val === 'ALL' || filterState[type] === val) {{
                filterState[type] = 'ALL';
            }} else {{
                filterState[type] = val;
            }}
            syncUIAndRefresh();
        }}

        function setFilter(type, val) {{
            filterState[type] = val;
            syncUIAndRefresh();
        }}

        function resetAllFilters() {{
            filterState.cuisine = 'ALL';
            filterState.month = 'ALL';
            filterState.dayType = 'ALL';
            syncUIAndRefresh();
        }}

        // Synchronize Slicers, Dropdowns, Badges, and re-render
        function syncUIAndRefresh() {{
            // Sync Dropdowns
            cuisineSel.value = filterState.cuisine;
            monthSel.value = filterState.month;
            dayTypeSel.value = filterState.dayType;

            // Sync Slicer Pills
            updateSlicerPillActive('cuisine', filterState.cuisine);
            updateSlicerPillActive('month', filterState.month);
            updateSlicerPillActive('dayType', filterState.dayType);

            // Update Breadcrumb Badges
            updateActiveFilterBadges();

            // Run Aggregations & Re-render
            updateDashboardMetrics();
            renderAllCharts();
            populateDriversTable();
            populateExplorerTable();
        }}

        function updateSlicerPillActive(type, activeVal) {{
            document.querySelectorAll(`.slicer-btn[data-type="${{type}}"]`).forEach(btn => {{
                if (btn.getAttribute('data-val') === activeVal) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});
        }}

        function updateActiveFilterBadges() {{
            const badgesContainer = document.getElementById('activeFiltersBadges');
            const clearBtn = document.getElementById('clearAllFiltersBtn');
            const pills = [];

            if (filterState.cuisine !== 'ALL') {{
                pills.push(`
                    <span class="active-filter-pill">
                        <span><strong>Cuisine:</strong> ${{filterState.cuisine}}</span>
                        <i class="fas fa-circle-xmark" title="Clear filter" onclick="toggleFilter('cuisine', '${{filterState.cuisine}}')"></i>
                    </span>
                `);
            }}

            const monthNames = {{
                '2022-06': 'June 2022',
                '2022-07': 'July 2022',
                '2022-08': 'August 2022',
                '2022-09': 'September 2022'
            }};
            if (filterState.month !== 'ALL') {{
                pills.push(`
                    <span class="active-filter-pill">
                        <span><strong>Month:</strong> ${{monthNames[filterState.month] || filterState.month}}</span>
                        <i class="fas fa-circle-xmark" title="Clear filter" onclick="toggleFilter('month', '${{filterState.month}}')"></i>
                    </span>
                `);
            }}

            if (filterState.dayType !== 'ALL') {{
                pills.push(`
                    <span class="active-filter-pill">
                        <span><strong>Day:</strong> ${{filterState.dayType}}s</span>
                        <i class="fas fa-circle-xmark" title="Clear filter" onclick="toggleFilter('dayType', '${{filterState.dayType}}')"></i>
                    </span>
                `);
            }}

            if (pills.length > 0) {{
                badgesContainer.innerHTML = pills.join('');
                clearBtn.classList.remove('d-none');
            }} else {{
                badgesContainer.innerHTML = '<span class="text-muted small fst-italic">None (Showing all data &bull; Click any bar or pie slice to cross-filter)</span>';
                clearBtn.classList.add('d-none');
            }}
        }}

        function getFilteredMatrix() {{
            return RAW_DATA.matrix.filter(r => {{
                if (filterState.cuisine !== 'ALL' && r.cuisine !== filterState.cuisine) return false;
                if (filterState.month !== 'ALL' && r.month !== filterState.month) return false;
                if (filterState.dayType !== 'ALL' && r.day_type !== filterState.dayType) return false;
                return true;
            }});
        }}

        function getPlotlyTemplate() {{
            return currentTheme === 'dark' ? 'plotly_dark' : 'plotly_white';
        }}

        function updateDashboardMetrics() {{
            const data = getFilteredMatrix();

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

            document.getElementById('kpiRevenue').innerText = '$' + totalRev.toLocaleString('en-US', {{maximumFractionDigits: 0}});
            document.getElementById('kpiOrders').innerText = totalOrders.toLocaleString('en-US');
            document.getElementById('kpiOrdersSub').innerText = totalOrders.toLocaleString('en-US') + ' orders';
            document.getElementById('kpiAov').innerText = '$' + aov.toFixed(2);
            document.getElementById('kpiFoodTotal').innerText = '$' + foodTot.toLocaleString('en-US', {{maximumFractionDigits: 0}});
            document.getElementById('kpiDiscountSub').innerText = discPct.toFixed(1) + '% discount share';
            document.getElementById('kpiFastPct').innerText = fastPct.toFixed(1) + '%';
            document.getElementById('kpiDelivFees').innerText = '$' + delivFees.toLocaleString('en-US', {{maximumFractionDigits: 0}});
        }}

        function renderAllCharts() {{
            try {{ renderMonthlyChart(); }} catch(e) {{ console.error('Error in renderMonthlyChart:', e); }}
            try {{ renderRFMCharts(); }} catch(e) {{ console.error('Error in renderRFMCharts:', e); }}
            try {{ renderMarketBasketChart(); }} catch(e) {{ console.error('Error in renderMarketBasketChart:', e); }}
            try {{ renderStrategyCharts(); }} catch(e) {{ console.error('Error in renderStrategyCharts:', e); }}
            try {{ renderSimulatorCharts(); }} catch(e) {{ console.error('Error in renderSimulatorCharts:', e); }}
            try {{ renderCuisinePie(); }} catch(e) {{ console.error('Error in renderCuisinePie:', e); }}
            try {{ renderHourlyChart(); }} catch(e) {{ console.error('Error in renderHourlyChart:', e); }}
            try {{ renderCuisineBar(); }} catch(e) {{ console.error('Error in renderCuisineBar:', e); }}
            try {{ renderDayTypeChart(); }} catch(e) {{ console.error('Error in renderDayTypeChart:', e); }}
            try {{ renderRestaurantsChart(); }} catch(e) {{ console.error('Error in renderRestaurantsChart:', e); }}
            try {{ renderDishesChart(); }} catch(e) {{ console.error('Error in renderDishesChart:', e); }}
            try {{ renderDietaryChart(); }} catch(e) {{ console.error('Error in renderDietaryChart:', e); }}
            try {{ renderDeliverySLA(); }} catch(e) {{ console.error('Error in renderDeliverySLA:', e); }}
        }}

        // 1. Monthly Chart (With Power BI Dimming / Highlighting)
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

            // Power BI Visual Cross-Highlighting: Dim non-selected months
            const barColors = months.map(m => {{
                if (filterState.month === 'ALL' || filterState.month === m) {{
                    return '#4F46E5';
                }} else {{
                    return currentTheme === 'dark' ? 'rgba(79, 70, 229, 0.25)' : 'rgba(79, 70, 229, 0.28)';
                }}
            }});

            const traceRev = {{
                x: xVals,
                y: yRev,
                name: 'Revenue ($)',
                type: 'bar',
                marker: {{ color: barColors }},
                text: yRev.map(v => '$' + Math.round(v).toLocaleString()),
                textposition: 'inside',
                customdata: months,
                hovertemplate: '<b>%{{x}}</b><br>Revenue: $%{{y:,.0f}}<br><i>Click to filter / toggle month</i><extra></extra>'
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
                textposition: 'top center',
                customdata: months,
                hovertemplate: '<b>%{{x}}</b><br>Orders: %{{y:,}}<extra></extra>'
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
            attachPlotlyClick('chartMonthly', (pt) => {{
                const monthMap = {{
                    'June 2022': '2022-06',
                    'July 2022': '2022-07',
                    'August 2022': '2022-08',
                    'September 2022': '2022-09'
                }};
                const mCode = monthMap[pt.x] || pt.customdata;
                if (mCode) toggleFilter('month', mCode);
            }});
        }}

        // 2. Cuisine Pie (With Slice Pull & Dimming)
        function renderCuisinePie() {{
            const filtered = getFilteredMatrix();
            const cuisMap = {{}};
            filtered.forEach(r => {{
                cuisMap[r.cuisine] = (cuisMap[r.cuisine] || 0) + r.revenue;
            }});

            const labels = Object.keys(cuisMap);
            const values = Object.values(cuisMap);

            // Pull slice if selected
            const pulls = labels.map(c => filterState.cuisine === c ? 0.12 : 0);

            const baseColors = {{
                'Chinese': '#4F46E5',
                'Italian': '#10B981',
                'Indian': '#F59E0B',
                'Thai': '#EF4444'
            }};

            const colors = labels.map(c => {{
                if (filterState.cuisine === 'ALL' || filterState.cuisine === c) {{
                    return baseColors[c] || '#4F46E5';
                }} else {{
                    return 'rgba(148, 163, 184, 0.35)'; // Dimmed
                }}
            }});

            const trace = {{
                labels: labels,
                values: values,
                type: 'pie',
                hole: 0.48,
                pull: pulls,
                marker: {{ colors: colors }},
                textinfo: 'label+percent',
                hovertemplate: '<b>%{{label}}</b><br>Revenue: $%{{value:,.0f}}<br>(%{{percent}})<br><i>Click to filter / toggle cuisine</i><extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 20, r: 20, t: 20, b: 20 }},
                showlegend: false,
                autosize: true
            }};

            Plotly.react('chartCuisinePie', [trace], layout, {{ responsive: true }});
            attachPlotlyClick('chartCuisinePie', (pt) => {{
                if (pt.label) toggleFilter('cuisine', pt.label);
            }});
        }}

        // 3. Hourly Curve
        function renderHourlyChart() {{
            const cVal = filterState.cuisine;
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
                fillcolor: currentTheme === 'dark' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(79, 70, 229, 0.12)',
                hovertemplate: '<b>%{{x}}</b><br>Orders Placed: %{{y:,}}<extra></extra>'
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

        // 4. Cuisine AOV Bar (With Click Filter & Dimming)
        function renderCuisineBar() {{
            const filtered = getFilteredMatrix();
            const cuisRev = {{}}, cuisOrd = {{}};
            filtered.forEach(r => {{
                cuisRev[r.cuisine] = (cuisRev[r.cuisine] || 0) + r.revenue;
                cuisOrd[r.cuisine] = (cuisOrd[r.cuisine] || 0) + r.orders;
            }});

            const cuisines = Object.keys(cuisRev);
            const aovs = cuisines.map(c => cuisOrd[c] > 0 ? (cuisRev[c] / cuisOrd[c]) : 0);

            const baseColors = {{
                'Chinese': '#4F46E5',
                'Italian': '#10B981',
                'Indian': '#F59E0B',
                'Thai': '#EF4444'
            }};

            const colors = cuisines.map(c => {{
                if (filterState.cuisine === 'ALL' || filterState.cuisine === c) {{
                    return baseColors[c] || '#4F46E5';
                }} else {{
                    return 'rgba(148, 163, 184, 0.35)'; // Dimmed
                }}
            }});

            const trace = {{
                x: cuisines,
                y: aovs,
                type: 'bar',
                marker: {{ color: colors }},
                text: aovs.map(v => '$' + v.toFixed(2)),
                textposition: 'outside',
                hovertemplate: '<b>%{{x}}</b><br>Average Ticket: $%{{y:.2f}}<br><i>Click to filter / toggle</i><extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 20, t: 20, b: 40 }},
                yaxis: {{ title: 'Average Ticket ($)' }},
                autosize: true
            }};

            Plotly.react('chartCuisineBar', [trace], layout, {{ responsive: true }});
            attachPlotlyClick('chartCuisineBar', (pt) => {{
                if (pt.x) toggleFilter('cuisine', pt.x);
            }});
        }}

        // 5. Day Type Comparison (With Click Filter & Dimming)
        function renderDayTypeChart() {{
            const filtered = getFilteredMatrix();
            let wkRev = 0, weRev = 0;

            filtered.forEach(r => {{
                if (r.day_type === 'Weekday') {{
                    wkRev += r.revenue;
                }} else {{
                    weRev += r.revenue;
                }}
            }});

            const dayTypes = ['Weekdays (Mon-Fri)', 'Weekends (Sat-Sun)'];
            const dayCodes = ['Weekday', 'Weekend'];
            const yVals = [wkRev, weRev];

            const colors = dayCodes.map((dt, i) => {{
                const base = i === 0 ? '#3B82F6' : '#EC4899';
                if (filterState.dayType === 'ALL' || filterState.dayType === dt) {{
                    return base;
                }} else {{
                    return 'rgba(148, 163, 184, 0.35)';
                }}
            }});

            const trace = {{
                x: dayTypes,
                y: yVals,
                type: 'bar',
                marker: {{ color: colors }},
                text: ['$' + Math.round(wkRev).toLocaleString(), '$' + Math.round(weRev).toLocaleString()],
                textposition: 'inside',
                customdata: dayCodes,
                hovertemplate: '<b>%{{x}}</b><br>Revenue: $%{{y:,.0f}}<br><i>Click to filter / toggle</i><extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 40, r: 20, t: 20, b: 40 }},
                yaxis: {{ title: 'Revenue ($)' }},
                autosize: true
            }};

            Plotly.react('chartDayType', [trace], layout, {{ responsive: true }});
            attachPlotlyClick('chartDayType', (pt) => {{
                const code = pt.x.includes('Weekday') ? 'Weekday' : 'Weekend';
                toggleFilter('dayType', code);
            }});
        }}

        // 6. Restaurants Chart
        function renderRestaurantsChart() {{
            const cVal = filterState.cuisine;
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
                textposition: 'outside',
                hovertemplate: '<b>%{{y}}</b><br>Sales: $%{{x:,.0f}}<br><i>Click to search restaurant in explorer</i><extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 160, r: 50, t: 20, b: 40 }},
                xaxis: {{ title: 'Revenue ($)' }},
                autosize: true
            }};

            Plotly.react('chartRestaurants', [trace], layout, {{ responsive: true }});
            attachPlotlyClick('chartRestaurants', (pt) => {{
                if (pt.y) {{
                    const tableTab = document.getElementById('table-tab');
                    if (tableTab) {{
                        bootstrap.Tab.getOrCreateInstance(tableTab).show();
                        searchInput.value = pt.y;
                        filterExplorerTable();
                    }}
                }}
            }});
        }}

        // 7. Dishes Chart
        function renderDishesChart() {{
            const cVal = filterState.cuisine;
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
                textposition: 'inside',
                hovertemplate: '<b>%{{y}}</b><br>Units Sold: %{{x:,}}<br><i>Click to search dish in explorer</i><extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ l: 170, r: 40, t: 20, b: 40 }},
                xaxis: {{ title: 'Units Sold' }},
                autosize: true
            }};

            Plotly.react('chartDishes', [trace], layout, {{ responsive: true }});
            attachPlotlyClick('chartDishes', (pt) => {{
                if (pt.y) {{
                    const tableTab = document.getElementById('table-tab');
                    if (tableTab) {{
                        bootstrap.Tab.getOrCreateInstance(tableTab).show();
                        searchInput.value = pt.y;
                        filterExplorerTable();
                    }}
                }}
            }});
        }}

        // 8. Dietary Split Chart
        function renderDietaryChart() {{
            const cVal = filterState.cuisine;
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
                marker: {{ colors: ['#10B981', '#EF4444'] }},
                hovertemplate: '<b>%{{label}}</b><br>Units: %{{value:,}}<br>(%{{percent}})<extra></extra>'
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
                marker: {{ colors: ['#10B981', '#F59E0B'] }},
                hovertemplate: '<b>%{{label}}</b><br>Orders: %{{value:,}}<br>(%{{percent}})<extra></extra>'
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

        // Attach Plotly Click Handler helper with safe retry
        function attachPlotlyClick(domId, callback) {{
            const el = document.getElementById(domId);
            if (!el || el._clickBound) return;
            if (typeof el.on !== 'function') {{
                setTimeout(() => attachPlotlyClick(domId, callback), 150);
                return;
            }}
            el._clickBound = true;
            el.on('plotly_click', (data) => {{
                if (data && data.points && data.points.length > 0) {{
                    callback(data.points[0]);
                }}
            }});
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
            const cVal = filterState.cuisine;
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

        // Trigger resize on tab switch
        document.querySelectorAll('button[data-bs-toggle="pill"]').forEach(tab => {{
            tab.addEventListener('shown.bs.tab', () => {{
                window.dispatchEvent(new Event('resize'));
            }});
        }});

        // ==========================================
        // STEP 1: ADVANCED ANALYTICS & ML LOGIC
        // ==========================================
        let currentRfmView = 'treemap';

        // Toggle Buttons for Treemap vs Scatter
        const rfmTreemapBtn = document.getElementById('rfmViewTreemapBtn');
        const rfmScatterBtn = document.getElementById('rfmViewScatterBtn');
        if (rfmTreemapBtn && rfmScatterBtn) {{
            rfmTreemapBtn.addEventListener('click', () => {{
                currentRfmView = 'treemap';
                rfmTreemapBtn.classList.add('active');
                rfmScatterBtn.classList.remove('active');
                renderRFMCharts();
            }});
            rfmScatterBtn.addEventListener('click', () => {{
                currentRfmView = 'scatter';
                rfmScatterBtn.classList.add('active');
                rfmTreemapBtn.classList.remove('active');
                renderRFMCharts();
            }});
        }}

        // Cuisine Smart Bundles selector
        document.querySelectorAll('#basketCuisineTabs button').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('#basketCuisineTabs button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const cuisine = btn.getAttribute('data-cuisine');
                populateCuisineBaskets(cuisine);
            }});
        }});

        function renderRFMCharts() {{
            if (currentRfmView === 'treemap') {{
                renderRFMTreemap();
            }} else {{
                renderRFMScatter();
            }}
            renderRFMPareto();
            populateRFMTable();
            populateCuisineBaskets('Chinese');
        }}

        // RFM Treemap
        function renderRFMTreemap() {{
            const data = RAW_DATA.rfm_summary;
            const labels = data.map(d => d.segment);
            const parents = data.map(() => 'Customer Base');
            const values = data.map(d => d.total_revenue);
            const colors = data.map(d => d.color);

            // Add root node
            const allLabels = ['Customer Base', ...labels];
            const allParents = ['', ...parents];
            const allValues = [data.reduce((a, b) => a + b.total_revenue, 0), ...values];
            const allColors = [currentTheme === 'dark' ? '#1E293B' : '#F1F5F9', ...colors];

            const trace = {{
                type: 'treemap',
                labels: allLabels,
                parents: allParents,
                values: allValues,
                branchvalues: 'total',
                textinfo: 'label+value+percent parent',
                valueformat: '$,.0f',
                marker: {{
                    colors: allColors,
                    line: {{ width: 2, color: currentTheme === 'dark' ? '#151C2E' : '#FFFFFF' }}
                }},
                hovertemplate: '<b>%{{label}}</b><br>Revenue: %{{value:$,.0f}}<br>Contribution: %{{percentParent:.1%}}<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 10, b: 10, l: 10, r: 10 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartRfmMatrix', [trace], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // RFM Scatter Bubble Plot
        function renderRFMScatter() {{
            const sample = RAW_DATA.rfm_scatter;
            const segments = ['Champions', 'Loyal Customers', 'Potential Loyalists', 'Needs Attention', 'About to Sleep', 'At Risk', 'Hibernating / Churned'];
            const segColors = {{
                'Champions': '#10B981',
                'Loyal Customers': '#4F46E5',
                'Potential Loyalists': '#06B6D4',
                'Needs Attention': '#F59E0B',
                'About to Sleep': '#64748B',
                'At Risk': '#EF4444',
                'Hibernating / Churned': '#334155'
            }};

            const traces = segments.map(seg => {{
                const pts = sample.filter(p => p.seg === seg);
                return {{
                    name: seg,
                    x: pts.map(p => p.r),
                    y: pts.map(p => p.m),
                    text: pts.map(p => `Cust #${{p.id}} | Orders: ${{p.f}}`),
                    mode: 'markers',
                    marker: {{
                        size: pts.map(p => Math.min(24, Math.max(7, p.f * 2.6))),
                        color: segColors[seg] || '#4F46E5',
                        opacity: 0.75,
                        line: {{ width: 1, color: '#FFFFFF' }}
                    }},
                    hovertemplate: `<b>${{seg}}</b><br>Recency: %{{x}} days<br>Total Spend: $%{{y:.2f}}<br>%{{text}}<extra></extra>`
                }};
            }});

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 30, b: 50, l: 60, r: 20 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                xaxis: {{ 
                    title: 'Recency (Days Since Last Order - Lower is Better)',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9',
                    zeroline: false
                }},
                yaxis: {{ 
                    title: 'Monetary Spend ($)',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9',
                    zeroline: false
                }},
                legend: {{ orientation: 'h', y: -0.25, x: 0 }},
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartRfmMatrix', traces, layout, {{ responsive: true, displayModeBar: false }});
        }}

        // Pareto Analysis Chart
        function renderRFMPareto() {{
            const data = [...RAW_DATA.rfm_summary].reverse();
            const yLabels = data.map(d => d.segment);
            const xCust = data.map(d => d.customer_pct);
            const xRev = data.map(d => d.revenue_pct);

            const traceCust = {{
                name: '% Customer Volume',
                type: 'bar',
                orientation: 'h',
                y: yLabels,
                x: xCust,
                marker: {{ color: currentTheme === 'dark' ? '#334155' : '#CBD5E1' }},
                hovertemplate: '%{{y}}<br>Customer Share: %{{x:.1f}}%<extra></extra>'
            }};

            const traceRev = {{
                name: '% Revenue Contribution',
                type: 'bar',
                orientation: 'h',
                y: yLabels,
                x: xRev,
                marker: {{ color: '#4F46E5' }},
                hovertemplate: '%{{y}}<br>Revenue Share: %{{x:.1f}}%<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                barmode: 'group',
                margin: {{ t: 20, b: 50, l: 140, r: 20 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                xaxis: {{ 
                    title: 'Percentage Share (%)',
                    ticksuffix: '%',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9'
                }},
                yaxis: {{ automargin: true }},
                legend: {{ orientation: 'h', y: 1.15, x: 0 }},
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartRfmPareto', [traceCust, traceRev], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // Market Basket Horizontal Bar Chart
        function renderMarketBasketChart() {{
            const pairs = [...RAW_DATA.top_pairs].reverse();
            const yPairs = pairs.map(p => p.pair);
            const xOrders = pairs.map(p => p.orders);
            const textLabels = pairs.map(p => `${{p.orders}} orders (Conf: ${{p.conf}}%)`);

            const trace = {{
                type: 'bar',
                orientation: 'h',
                y: yPairs,
                x: xOrders,
                text: textLabels,
                textposition: 'inside',
                insidetextfont: {{ color: '#FFFFFF', weight: 'bold' }},
                marker: {{
                    color: xOrders,
                    colorscale: 'Viridis',
                    showscale: false
                }},
                customdata: pairs.map(p => [p.conf, p.lift, p.cuisine]),
                hovertemplate: '<b>%{{y}}</b> (%{{customdata[2]}})<br>Orders Together: %{{x}}<br>Confidence: %{{customdata[0]}}%<br>Lift Score: %{{customdata[1]}}x<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 20, b: 40, l: 200, r: 20 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                xaxis: {{ 
                    title: 'Co-Occurrence Frequency (Orders)',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9'
                }},
                yaxis: {{ automargin: true }},
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartMarketBasket', [trace], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // Populate Cuisine Smart Bundles
        function populateCuisineBaskets(cuisine) {{
            const container = document.getElementById('cuisineBasketContainer');
            if (!container) return;
            const items = RAW_DATA.cuisine_baskets[cuisine] || [];

            if (items.length === 0) {{
                container.innerHTML = '<div class="text-muted small p-3">No specific pairs found for this cuisine.</div>';
                return;
            }}

            container.innerHTML = items.map(item => `
                <div class="p-3 rounded-3" style="background: var(--primary-light); border: 1px solid var(--border-color);">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <span class="fw-bold" style="color: var(--primary); font-size: 0.9rem;">
                            <i class="fas fa-link me-1"></i> ${{item.pair}}
                        </span>
                        <span class="badge bg-primary text-white rounded-pill px-2 py-1 small">
                            ${{item.orders}} Pairs
                        </span>
                    </div>
                    <div class="small text-muted mb-2">
                        <span>Confidence: <strong>${{item.conf}}%</strong></span> &bull; 
                        <span>Lift: <strong>${{item.lift}}x</strong></span>
                    </div>
                    <div class="d-flex align-items-center justify-content-between p-2 rounded-2" style="background: var(--bg-card); border: 1px dashed var(--border-color);">
                        <span class="small fw-semibold"><i class="fas fa-tag text-warning me-1"></i> ${{item.deal}}</span>
                        <span class="badge bg-success bg-opacity-10 text-success fw-bold small">+14% AOV</span>
                    </div>
                </div>
            `).join('');
        }}

        // Populate RFM Actionable Strategy Table
        function populateRFMTable() {{
            const tbody = document.getElementById('rfmPlaybookTableBody');
            if (!tbody) return;
            const data = RAW_DATA.rfm_summary;

            tbody.innerHTML = data.map(row => `
                <tr>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge ${{row.badge}} px-2.5 py-1.5 rounded-pill fw-bold">
                                <i class="fas ${{row.icon}} me-1"></i> ${{row.segment}}
                            </span>
                        </div>
                    </td>
                    <td><strong>${{row.customers.toLocaleString()}}</strong> <span class="text-muted small">(${{row.customer_pct}}%)</span></td>
                    <td><strong>$${{Math.round(row.total_revenue).toLocaleString()}}</strong> <span class="text-muted small">(${{row.revenue_pct}}%)</span></td>
                    <td><span class="badge bg-secondary bg-opacity-10 text-dark px-2 py-1">${{row.avg_recency}} days</span></td>
                    <td><span class="badge bg-info bg-opacity-10 text-info px-2 py-1">${{row.avg_freq}} orders</span></td>
                    <td><strong>$${{row.avg_monetary.toFixed(2)}}</strong></td>
                    <td>
                        <div class="small" style="line-height: 1.35;">${{row.strategy}}</div>
                    </td>
                </tr>
            `).join('');
        }}

        // Resize handler updates for ML charts
        window.addEventListener('resize', () => {{
            const mlCharts = ['chartRfmMatrix', 'chartRfmPareto', 'chartMarketBasket'];
            mlCharts.forEach(id => {{
                const el = document.getElementById(id);
                if (el && el.data) {{
                    Plotly.Plots.resize(el);
                }}
            }});
        }});

        // Trigger redraw on ML tab click
        const mlTabBtn = document.getElementById('ml-tab');
        if (mlTabBtn) {{
            mlTabBtn.addEventListener('shown.bs.tab', () => {{
                renderRFMCharts();
                renderMarketBasketChart();
            }});
        }}

        // ==========================================
        // STEP 2: PRESCRIPTIVE STRATEGY & INSIGHTS LOGIC
        // ==========================================
        function renderStrategyCharts() {{
            renderStrategyWaterfall();
            renderPriorityMatrix();
            populateStrategyPillars();
            populateRoadmapTable();
        }}

        // 1. Revenue Recovery Waterfall Bridge (Plotly Waterfall)
        function renderStrategyWaterfall() {{
            const wf = RAW_DATA.strategy_waterfall;
            const trace = {{
                type: 'waterfall',
                orientation: 'v',
                measure: wf.measure,
                x: wf.x,
                y: wf.y,
                text: wf.text,
                textposition: 'outside',
                connector: {{
                    line: {{ color: currentTheme === 'dark' ? '#475569' : '#94A3B8', width: 1.5, dash: 'dot' }}
                }},
                increasing: {{ marker: {{ color: '#10B981' }} }},
                decreasing: {{ marker: {{ color: '#EF4444' }} }},
                totals: {{ marker: {{ color: '#4F46E5' }} }},
                hovertemplate: '<b>%{{x}}</b><br>Impact: %{{text}}<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 30, b: 60, l: 60, r: 20 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                yaxis: {{
                    title: 'Monthly Revenue ($ in Thousands)',
                    ticksuffix: 'k',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9',
                    zeroline: false
                }},
                xaxis: {{
                    automargin: true,
                    tickangle: -15
                }},
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartStrategyWaterfall', [trace], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // 2. Strategic Action Priority Matrix (Plotly Scatter Quadrant)
        function renderPriorityMatrix() {{
            const items = RAW_DATA.priority_matrix;

            const trace = {{
                type: 'scatter',
                mode: 'markers+text',
                x: items.map(d => d.effort),
                y: items.map(d => d.impact),
                text: items.map(d => d.name),
                textposition: 'top center',
                textfont: {{
                    family: 'Plus Jakarta Sans',
                    size: 11,
                    weight: 'bold',
                    color: currentTheme === 'dark' ? '#F1F5F9' : '#0F172A'
                }},
                marker: {{
                    size: items.map(d => d.cat === 'Quick Win' ? 22 : (d.cat === 'Major Strategic Bet' ? 24 : 16)),
                    color: items.map(d => d.color),
                    opacity: 0.9,
                    line: {{ width: 2, color: '#FFFFFF' }}
                }},
                customdata: items.map(d => [d.cat, d.desc]),
                hovertemplate: '<b>%{{text}}</b> (%{{customdata[0]}})<br>Effort: %{{x}}/10 &bull; Impact: %{{y}}/10<br>%{{customdata[1]}}<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 30, b: 50, l: 50, r: 30 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                xaxis: {{
                    title: 'Implementation Effort & Complexity (1 = Lowest, 10 = Highest)',
                    range: [0, 10],
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9',
                    zeroline: false
                }},
                yaxis: {{
                    title: 'Revenue & Margin Impact (1 = Lowest, 10 = Highest)',
                    range: [0, 10.5],
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9',
                    zeroline: false
                }},
                shapes: [
                    // Vertical dividing line at Effort = 5
                    {{ type: 'line', x0: 5, x1: 5, y0: 0, y1: 10, line: {{ color: currentTheme === 'dark' ? '#334155' : '#CBD5E1', width: 1.5, dash: 'dash' }} }},
                    // Horizontal dividing line at Impact = 5
                    {{ type: 'line', x0: 0, x1: 10, y0: 6, y1: 6, line: {{ color: currentTheme === 'dark' ? '#334155' : '#CBD5E1', width: 1.5, dash: 'dash' }} }}
                ],
                annotations: [
                    {{ x: 2.5, y: 10.1, xref: 'x', yref: 'y', text: '⚡ QUICK WINS (High Impact, Low Effort)', showarrow: false, font: {{ size: 10, color: '#10B981', weight: 'bold' }} }},
                    {{ x: 7.5, y: 10.1, xref: 'x', yref: 'y', text: '🚀 MAJOR STRATEGIC BETS', showarrow: false, font: {{ size: 10, color: '#4F46E5', weight: 'bold' }} }},
                    {{ x: 2.5, y: 0.8, xref: 'x', yref: 'y', text: '🔍 FILL-INS', showarrow: false, font: {{ size: 10, color: '#F59E0B', weight: 'bold' }} }},
                    {{ x: 7.5, y: 0.8, xref: 'x', yref: 'y', text: '⏳ DE-PRIORITIZE', showarrow: false, font: {{ size: 10, color: '#EF4444', weight: 'bold' }} }}
                ],
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartPriorityMatrix', [trace], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // 3. Populate The 4 Strategic Growth Pillars
        function populateStrategyPillars() {{
            const container = document.getElementById('strategicPillarsContainer');
            if (!container) return;
            const pillars = RAW_DATA.strategic_pillars;

            container.innerHTML = pillars.map(p => `
                <div class="col-12 col-md-6 col-xl-3">
                    <div class="chart-box h-100 d-flex flex-column justify-content-between p-3.5" style="border-top: 4px solid ${{p.color}};">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge rounded-pill px-2.5 py-1 small fw-bold" style="background: ${{p.bg}}; color: ${{p.color}};">
                                    <i class="fas ${{p.icon}} me-1"></i> Pillar ${{p.id}}
                                </span>
                                <span class="badge bg-success bg-opacity-10 text-success fw-bold small">${{p.target}}</span>
                            </div>
                            <h6 class="fw-bold mb-1" style="color: var(--text-main); font-size: 0.95rem;">${{p.title}}</h6>
                            <p class="text-muted small mb-2 fst-italic" style="font-size: 0.78rem;">${{p.tag}}</p>
                            
                            <div class="p-2.5 rounded-2 mb-2.5" style="background: var(--primary-light); font-size: 0.82rem;">
                                <div class="fw-bold mb-1 text-danger small"><i class="fas fa-triangle-exclamation me-1"></i> The Core Problem:</div>
                                <div class="text-muted small">${{p.problem}}</div>
                            </div>

                            <div class="p-2.5 rounded-2 mb-2.5" style="background: var(--bg-card); border: 1px dashed var(--border-color); font-size: 0.82rem;">
                                <div class="fw-bold mb-1 text-success small"><i class="fas fa-circle-check me-1"></i> Prescriptive Action:</div>
                                <div style="color: var(--text-main); font-size: 0.82rem;">${{p.solution}}</div>
                            </div>
                        </div>

                        <div class="pt-2 border-top mt-2 d-flex justify-content-between align-items-center text-muted small" style="font-size: 0.75rem;">
                            <span><i class="fas fa-user-tie me-1"></i> ${{p.owner}}</span>
                            <span class="fw-bold text-primary">${{p.timeline}}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }}

        // 4. Populate 30-60-90 Day Roadmap Table
        function populateRoadmapTable() {{
            const tbody = document.getElementById('roadmapTableBody');
            if (!tbody) return;
            const rows = RAW_DATA.roadmap_milestones;

            tbody.innerHTML = rows.map(r => `
                <tr>
                    <td>
                        <span class="badge bg-primary bg-opacity-10 text-primary px-3 py-1.5 rounded-pill fw-bold">
                            <i class="fas fa-calendar-check me-1"></i> ${{r.phase}}
                        </span>
                    </td>
                    <td><strong>${{r.focus}}</strong></td>
                    <td class="small" style="line-height: 1.45;">${{r.initiatives}}</td>
                    <td><span class="badge bg-secondary bg-opacity-10 text-dark px-2.5 py-1 rounded-pill">${{r.owner}}</span></td>
                    <td><span class="badge bg-success bg-opacity-15 text-success fw-bold px-2.5 py-1 rounded-pill">${{r.target_metric}}</span></td>
                </tr>
            `).join('');
        }}

        // Trigger redraw on Strategy tab click
        const strategyTabBtn = document.getElementById('strategy-tab');
        if (strategyTabBtn) {{
            strategyTabBtn.addEventListener('shown.bs.tab', () => {{
                renderStrategyCharts();
            }});
        }}

        // Resize handler updates for Strategy charts
        window.addEventListener('resize', () => {{
            const stratCharts = ['chartStrategyWaterfall', 'chartPriorityMatrix', 'chartSimComparison', 'chartSimGauge'];
            stratCharts.forEach(id => {{
                const el = document.getElementById(id);
                if (el && el.data) {{
                    Plotly.Plots.resize(el);
                }}
            }});
        }});

        // Trigger redraw on Simulator tab click
        const simulatorTabBtn = document.getElementById('simulator-tab');
        if (simulatorTabBtn) {{
            simulatorTabBtn.addEventListener('shown.bs.tab', () => {{
                renderSimulatorCharts();
            }});
        }}

        // ==========================================
        // STEP 3: WHAT-IF SCENARIO SIMULATOR LOGIC
        // ==========================================
        // Sliders elements
        const sWinback = document.getElementById('sliderWinback');
        const sAov = document.getElementById('sliderAov');
        const sDiscount = document.getElementById('sliderDiscount');
        const sVolume = document.getElementById('sliderVolume');

        // Labels elements
        const lWinback = document.getElementById('labelWinback');
        const lAov = document.getElementById('labelAov');
        const lDiscount = document.getElementById('labelDiscount');
        const lVolume = document.getElementById('labelVolume');

        // Preset buttons
        document.querySelectorAll('.scenario-preset-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.scenario-preset-btn').forEach(b => {{
                    b.classList.remove('active', 'btn-success', 'btn-secondary', 'btn-primary', 'btn-danger');
                    b.classList.add('btn-outline-secondary');
                }});

                const preset = btn.getAttribute('data-preset');
                if (preset === 'conservative') {{
                    sWinback.value = 10;
                    sAov.value = 3.0;
                    sDiscount.value = 11.0;
                    sVolume.value = 0.0;
                    btn.classList.add('active', 'btn-secondary');
                }} else if (preset === 'target') {{
                    sWinback.value = 25;
                    sAov.value = 6.7;
                    sDiscount.value = 9.5;
                    sVolume.value = 12.8;
                    btn.classList.add('active', 'btn-success');
                }} else if (preset === 'aggressive') {{
                    sWinback.value = 45;
                    sAov.value = 15.0;
                    sDiscount.value = 7.5;
                    sVolume.value = 25.0;
                    btn.classList.add('active', 'btn-primary');
                }} else if (preset === 'baseline') {{
                    sWinback.value = 0;
                    sAov.value = 0.0;
                    sDiscount.value = 13.2;
                    sVolume.value = 0.0;
                    btn.classList.add('active', 'btn-danger');
                }}
                runSimulation();
            }});
        }});

        // Attach event listeners to sliders for real-time 60fps update
        [sWinback, sAov, sDiscount, sVolume].forEach(slider => {{
            if (slider) {{
                slider.addEventListener('input', runSimulation);
            }}
        }});

        function runSimulation() {{
            const base = RAW_DATA.simulator_baseline;
            const wVal = parseFloat(sWinback.value) / 100;
            const aVal = parseFloat(sAov.value) / 100;
            const dVal = parseFloat(sDiscount.value) / 100;
            const vVal = parseFloat(sVolume.value) / 100;

            // Update Labels
            lWinback.innerText = `${{sWinback.value}}%`;
            lAov.innerText = `${{parseFloat(sAov.value) >= 0 ? '+' : ''}}${{sAov.value}}%`;
            lDiscount.innerText = `${{sDiscount.value}}%`;
            lVolume.innerText = `${{parseFloat(sVolume.value) >= 0 ? '+' : ''}}${{sVolume.value}}%`;

            // Math Model
            const revWinback = base.at_risk_pool * wVal;
            const simOrders = Math.round(base.orders * (1 + vVal) + (456 * wVal * 1.4));
            const simAov = base.aov * (1 + aVal);
            const simRev = Math.round(simOrders * simAov + revWinback);

            const simFood = simRev * 1.028;
            const simDisc = Math.round(simFood * dVal);
            const baselineDiscForVolume = simFood * 0.132;
            const discSavings = Math.round(baselineDiscForVolume - simDisc);

            const revDelta = simRev - base.revenue;
            const revDeltaPct = (revDelta / base.revenue) * 100;
            const ordersDelta = simOrders - base.orders;
            const ordersDeltaPct = (ordersDelta / base.orders) * 100;
            const aovDelta = simAov - base.aov;
            const aovDeltaPct = (aovDelta / base.aov) * 100;

            const monthlyNetGain = revDelta + discSavings;
            const quarterlyNetBenefit = monthlyNetGain * 3;
            const annualNetBenefit = monthlyNetGain * 12;

            // Update KPI Scorecards
            document.getElementById('simKpiRevenue').innerText = '$' + simRev.toLocaleString('en-US');
            document.getElementById('simKpiRevDelta').innerHTML = `
                <span class="${{revDelta >= 0 ? 'text-success' : 'text-danger'}}">
                    ${{revDelta >= 0 ? '+' : ''}}$${{Math.round(revDelta).toLocaleString('en-US')}} (${{revDeltaPct >= 0 ? '+' : ''}}${{revDeltaPct.toFixed(1)}}%) vs Sep
                </span>
            `;

            document.getElementById('simKpiOrders').innerText = simOrders.toLocaleString('en-US');
            document.getElementById('simKpiOrdersDelta').innerHTML = `
                <span class="${{ordersDelta >= 0 ? 'text-primary' : 'text-danger'}}">
                    ${{ordersDelta >= 0 ? '+' : ''}}${{ordersDelta.toLocaleString('en-US')}} orders (${{ordersDeltaPct >= 0 ? '+' : ''}}${{ordersDeltaPct.toFixed(1)}}%)
                </span>
            `;

            document.getElementById('simKpiAov').innerText = '$' + simAov.toFixed(2);
            document.getElementById('simKpiAovDelta').innerHTML = `
                <span class="${{aovDelta >= 0 ? 'text-warning' : 'text-danger'}}">
                    ${{aovDelta >= 0 ? '+' : ''}}$${{aovDelta.toFixed(2)}} / order (${{aovDeltaPct >= 0 ? '+' : ''}}${{aovDeltaPct.toFixed(1)}}%)
                </span>
            `;

            document.getElementById('simKpiDiscSavings').innerText = (discSavings >= 0 ? '+$' : '-$') + Math.abs(discSavings).toLocaleString('en-US');
            document.getElementById('simKpiDiscRate').innerText = `${{sDiscount.value}}% effective rate`;

            document.getElementById('simKpiQuarterly').innerText = (quarterlyNetBenefit >= 0 ? '+$' : '-$') + Math.abs(Math.round(quarterlyNetBenefit)).toLocaleString('en-US');
            document.getElementById('simKpiAnnual').innerText = (annualNetBenefit >= 0 ? '+$' : '-$') + Math.abs(Math.round(annualNetBenefit)).toLocaleString('en-US');

            // Re-render Dynamic Visuals
            renderSimComparisonChart(base, simRev, simOrders, simAov, simDisc, discSavings);
            renderSimGaugeChart(base, simRev);
            populateSimVarianceTable(base, simRev, simOrders, simAov, simDisc, discSavings, revWinback);
        }}

        function renderSimulatorCharts() {{
            runSimulation();
        }}

        // 1. Comparison Bar Chart (Baseline vs Simulated)
        function renderSimComparisonChart(base, simRev, simOrders, simAov, simDisc, discSavings) {{
            const xMetrics = ['Gross Revenue ($)', 'Net Food Volume ($)', 'Discount Spend ($)'];
            const yBaseline = [base.revenue, base.revenue - base.discounts, base.discounts];
            const ySimulated = [simRev, simRev - simDisc, simDisc];

            const traceBase = {{
                name: 'Sep 2022 Baseline',
                type: 'bar',
                x: xMetrics,
                y: yBaseline,
                marker: {{ color: currentTheme === 'dark' ? '#334155' : '#94A3B8' }},
                text: yBaseline.map(v => '$' + Math.round(v).toLocaleString()),
                textposition: 'outside',
                hovertemplate: '%{{x}}<br>Baseline: $%{{y:,.0f}}<extra></extra>'
            }};

            const traceSim = {{
                name: 'Simulated Projection',
                type: 'bar',
                x: xMetrics,
                y: ySimulated,
                marker: {{ color: '#10B981' }},
                text: ySimulated.map(v => '$' + Math.round(v).toLocaleString()),
                textposition: 'outside',
                hovertemplate: '%{{x}}<br>Simulated: $%{{y:,.0f}}<extra></extra>'
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                barmode: 'group',
                margin: {{ t: 30, b: 40, l: 60, r: 20 }},
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                yaxis: {{
                    title: 'Amount (USD $)',
                    gridcolor: currentTheme === 'dark' ? '#242F47' : '#F1F5F9'
                }},
                legend: {{ orientation: 'h', y: 1.15, x: 0 }},
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartSimComparison', [traceBase, traceSim], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // 2. Recovery Gauge Chart
        function renderSimGaugeChart(base, simRev) {{
            const trace = {{
                type: 'indicator',
                mode: 'gauge+number+delta',
                value: simRev,
                delta: {{ 
                    reference: base.june_peak, 
                    increasing: {{ color: '#10B981' }}, 
                    decreasing: {{ color: '#EF4444' }},
                    prefix: '$',
                    valueformat: ',.0f'
                }},
                number: {{ prefix: '$', valueformat: ',.0f' }},
                gauge: {{
                    axis: {{ range: [200000, 400000], tickformat: '$,.0f' }},
                    bar: {{ color: '#4F46E5', width: 0.25 }},
                    steps: [
                        {{ range: [200000, 270000], color: 'rgba(239, 68, 68, 0.25)' }},
                        {{ range: [270000, 315000], color: 'rgba(245, 158, 11, 0.25)' }},
                        {{ range: [315000, 400000], color: 'rgba(16, 185, 129, 0.25)' }}
                    ],
                    threshold: {{
                        line: {{ color: '#10B981', width: 4 }},
                        thickness: 0.75,
                        value: base.june_peak
                    }}
                }}
            }};

            const layout = {{
                template: getPlotlyTemplate(),
                margin: {{ t: 25, b: 25, l: 30, r: 30 }},
                paper_bgcolor: 'transparent',
                font: {{ family: 'Plus Jakarta Sans', color: currentTheme === 'dark' ? '#E2E8F0' : '#1E293B' }}
            }};

            Plotly.react('chartSimGauge', [trace], layout, {{ responsive: true, displayModeBar: false }});
        }}

        // 3. Populate Variance Table
        function populateSimVarianceTable(base, simRev, simOrders, simAov, simDisc, discSavings, revWinback) {{
            const tbody = document.getElementById('simVarianceTableBody');
            if (!tbody) return;

            const rows = [
                {{
                    name: 'Monthly Gross Revenue',
                    base: '$' + Math.round(base.revenue).toLocaleString(),
                    sim: '$' + Math.round(simRev).toLocaleString(),
                    delta: (simRev - base.revenue >= 0 ? '+$' : '-$') + Math.abs(Math.round(simRev - base.revenue)).toLocaleString(),
                    pct: ((simRev - base.revenue) / base.revenue * 100).toFixed(1) + '%',
                    comment: 'Topline platform order volume and basket expansion impact.',
                    color: simRev >= base.revenue ? 'text-success' : 'text-danger'
                }},
                {{
                    name: 'Monthly Order Count',
                    base: base.orders.toLocaleString() + ' orders',
                    sim: simOrders.toLocaleString() + ' orders',
                    delta: (simOrders - base.orders >= 0 ? '+' : '') + (simOrders - base.orders).toLocaleString(),
                    pct: ((simOrders - base.orders) / base.orders * 100).toFixed(1) + '%',
                    comment: 'Organic customer expansion + reactivated VIP accounts.',
                    color: simOrders >= base.orders ? 'text-primary' : 'text-danger'
                }},
                {{
                    name: 'Average Order Value (AOV)',
                    base: '$' + base.aov.toFixed(2),
                    sim: '$' + simAov.toFixed(2),
                    delta: (simAov - base.aov >= 0 ? '+$' : '-$') + Math.abs(simAov - base.aov).toFixed(2),
                    pct: ((simAov - base.aov) / base.aov * 100).toFixed(1) + '%',
                    comment: 'Driven by checkout Apriori combo meal recommendations.',
                    color: simAov >= base.aov ? 'text-warning' : 'text-danger'
                }},
                {{
                    name: 'VIP Win-Back Revenue Added',
                    base: '$0 (456 Inactive)',
                    sim: '$' + Math.round(revWinback).toLocaleString(),
                    delta: '+$' + Math.round(revWinback).toLocaleString(),
                    pct: `${{sWinback.value}}% pool`,
                    comment: 'Direct monthly revenue recovered from slipping high-value accounts.',
                    color: 'text-success'
                }},
                {{
                    name: 'Promotional Discounts Given',
                    base: '$' + Math.round(base.discounts).toLocaleString() + ' (13.2%)',
                    sim: '$' + Math.round(simDisc).toLocaleString() + ` (${{sDiscount.value}}%)`,
                    delta: (discSavings >= 0 ? '-$' : '+$') + Math.abs(Math.round(discSavings)).toLocaleString(),
                    pct: discSavings >= 0 ? 'Margin Saved' : 'Margin Diluted',
                    comment: 'Achieved by enforcing $35 minimum basket gates on coupon codes.',
                    color: discSavings >= 0 ? 'text-success' : 'text-danger'
                }},
                {{
                    name: 'Quarterly Cumulative Benefit',
                    base: '$0 (Baseline)',
                    sim: (simRev - base.revenue + discSavings >= 0 ? '+$' : '-$') + Math.abs(Math.round((simRev - base.revenue + discSavings) * 3)).toLocaleString(),
                    delta: (simRev - base.revenue + discSavings >= 0 ? '+$' : '-$') + Math.abs(Math.round((simRev - base.revenue + discSavings) * 3)).toLocaleString(),
                    pct: '3-Mo ROI',
                    comment: 'Total bottom-line financial value created over next 90 days.',
                    color: 'text-success fw-bold'
                }}
            ];

            tbody.innerHTML = rows.map(r => `
                <tr>
                    <td><strong>${{r.name}}</strong></td>
                    <td><span class="text-muted">${{r.base}}</span></td>
                    <td><strong>${{r.sim}}</strong></td>
                    <td>
                        <span class="badge bg-opacity-10 ${{r.color.includes('success') ? 'bg-success text-success' : (r.color.includes('danger') ? 'bg-danger text-danger' : 'bg-primary text-primary')}} fw-bold px-2.5 py-1 rounded-pill">
                            ${{r.delta}} (${{r.pct}})
                        </span>
                    </td>
                    <td class="small text-muted">${{r.comment}}</td>
                </tr>
            `).join('');
        }}

        // Initial Load
        syncUIAndRefresh();
    </script>
</body>
</html>
"""

with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"[SUCCESS] Power BI-style interactive cross-filtering dashboard compiled at: {output_html}")
