# 🍔 FoodHunter Case Study & Interactive BI Dashboard

[![Live Dashboard](https://img.shields.io/badge/Live_Dashboard-GitHub_Pages-2ecc71?style=for-the-badge&logo=github)](https://sahil-093.github.io/foodhunter-case-study/)
[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)

> **Live Interactive Dashboard:** [https://sahil-093.github.io/foodhunter-case-study/](https://sahil-093.github.io/foodhunter-case-study/)

---

## 📌 Project Overview

This is an end-to-end data analytics and business intelligence project on the **FoodHunter** dataset from the Coursera course *Data Analytics Using SQL*. It features:
* An indexed **SQLite database (`foodhunter.db`)** parsed from the original MySQL dump containing **43,118 orders**, **10,000 customers**, **100 restaurants**, and **250 drivers**.
* A modern **Executive Web Dashboard (`index.html`)** hosted live via **GitHub Pages**.
* A full-fledged **Streamlit Web Application (`app.py`)** with real-time sidebar filtering, interactive KPI cards, and CSV export.
* Automated Python visualization pipelines using **Pandas**, **Plotly**, **Matplotlib**, and **Seaborn**.

---

## 🚀 Key Performance Indicators (KPIs)

| Metric | Value | Insights |
| :--- | :--- | :--- |
| **Total Revenue** | **$1,197,706.00** | Net final price across all fulfilled orders |
| **Total Orders** | **43,118** | June 1, 2022 to September 29, 2022 |
| **Average Order Value (AOV)** | **$27.78** | Extremely consistent monthly basket spend |
| **Customer Retention** | **94.7%** | 9,349 out of 9,874 active customers ordered >1 time |
| **Average Delivery Time** | **23.4 mins** | 82.9% delivered under 30 minutes (0 orders > 45m) |
| **Fleet Utilization** | **100%** | All 250 couriers actively fulfilled orders |

---

## 📊 Core Case Study Findings

### 1. Revenue Decline Driven by Volume, Not Basket Size
* June generated **12,502 orders** and **$347,578** in final revenue.
* August generated **10,107 orders** and **$283,366**.
* Average spend stayed between **$27.57** and **$28.04** in every month.

The bill identity in this dataset is:
$$\text{final\_price} = \text{total\_price} + \text{delivery\_fee} - \text{discount}$$

* Food gross total: **$1,229,527**
* Delivery fees collected: **$131,859**
* Discounts granted: **$163,680** (13.3% of food gross total across 28,814 orders)
* **Weekday vs Weekend:** Weekday generated $870,423 across 31,412 orders ($27.71 avg); Weekend generated $327,283 across 11,706 orders ($27.96 avg).

### 2. Chinese Cuisine Leads Orders and Revenue
* **Italian** has the most partner locations (38) and the most menu items (104).
* **Chinese** has 29 restaurants but dominates revenue with **15,021 orders** and **$437,707** in revenue.
* **Italian:** 13,381 orders ($356,704 revenue).
* **Indian:** 8,785 orders ($232,918 revenue).
* **Thai:** 5,931 orders ($170,377 revenue).

### 3. Dish & Menu Insights
* Top dish overall: **Peking duck** (2,851 units sold).
* Top single-restaurant menu item: **Shrimp fried rice** at Casa Mono (341 units).
* 14 menu items were never ordered.

### 4. Logistics & Driver Fleet
* Average delivery time is **23.4 minutes** (Range: 10 to 41 minutes).
* **35,734 orders** arrived in under 30 minutes, and **zero** orders exceeded 45 minutes.
* Brandon Luft held the highest rating among high-volume drivers: **3.86 rating** on 159 orders.

---

## 🤖 Step 1: Advanced Analytics & Machine Learning (Portfolio Boost)

The latest update introduces unsupervised customer behavioral clustering and association rule mining directly into the interactive dashboard:

### 1. RFM (Recency, Frequency, Monetary) Customer Segmentation
* **Champions (15.1% of accounts | ,470 revenue):** High recency (avg 4.8 days) and high frequency (avg 6.4 orders). Generates **22.2%** of all company revenue.
* **Loyal Customers (13.1% of accounts | ,884 revenue):** Consistent ordering with high lifetime spend (.70 avg).
* **80/20 Pareto Principle Validated:** Together, Champions and Loyal Customers make up **28.2% of users but drive 41.2% of total revenue (,354)**.
* **Churn Prevention Alert (At-Risk VIPs):** **456 customers** with high historical spend (.30 avg) have slipped to an average recency of **57.2 days**, representing **,185 at risk**.
* **High Customer Stickiness:** **94.7%** repeat purchase rate across 9,874 active accounts.

### 2. Apriori Market Basket Analysis & Cross-Selling Engine
* **Co-Occurrence Mining:** Analyzed 64,727 order item transactions to uncover frequently paired dishes.
* **Top Overall Pairings:**
  * **Peking Duck + Hot & Sour Soup:** 49 co-occurrences.
  * **Spring Rolls + Hot & Sour Soup:** 39 co-occurrences.
  * **Peking Duck + Spring Rolls:** 38 co-occurrences.
* **Smart Combo Bundling:** Recommended automated combo meal incentives per cuisine with a projected **+,400 monthly cross-sell revenue uplift** (+14% average basket size expansion).

---

## 🛠️ How to Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/Sahil-093/foodhunter-case-study.git
cd foodhunter-case-study
```

### 2. Install required packages
```bash
pip install pandas numpy plotly streamlit matplotlib seaborn
```

### 3. Launch Streamlit BI App
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 4. View Standalone HTML Dashboard
Simply double-click `index.html` or open in any browser.
