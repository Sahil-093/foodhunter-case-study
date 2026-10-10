-- FoodHunter case study
-- Dataset: Coursera, Data Analytics Using SQL
-- Database: foodhunter
-- These queries reproduce the project findings.
-- Revenue by cuisine assigns each order to one restaurant:
-- the smallest restaurant_id on that order.
-- 14,300 orders contain items from more than one restaurant.

USE foodhunter;

-- 1. Order window and scale
SELECT MIN(order_date) AS first_order,
       MAX(order_date) AS last_order,
       COUNT(*) AS orders
FROM orders;

SELECT COUNT(*) AS customers FROM customers;

SELECT COUNT(DISTINCT customer_id) AS customers_who_ordered
FROM orders;

SELECT COUNT(*) AS customers_with_no_order
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_id IS NULL;

SELECT MIN(cnt) AS min_orders,
       ROUND(AVG(cnt), 2) AS avg_orders,
       MAX(cnt) AS max_orders
FROM (
    SELECT customer_id, COUNT(*) AS cnt
    FROM orders
    GROUP BY customer_id
) t;

SELECT COUNT(*) AS repeat_customers
FROM (
    SELECT customer_id
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) > 1
) t;

SELECT ROUND(SUM(final_price), 2) AS total_final_price,
       ROUND(AVG(final_price), 2) AS avg_final_price,
       ROUND(MIN(final_price), 2) AS min_final_price,
       ROUND(MAX(final_price), 2) AS max_final_price
FROM orders;

-- 2. Restaurants and cuisine
SELECT cuisine, COUNT(*) AS restaurants
FROM restaurants
GROUP BY cuisine
ORDER BY restaurants DESC;

SELECT COUNT(*) AS orders_with_multiple_restaurants
FROM (
    SELECT oi.order_id
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    GROUP BY oi.order_id
    HAVING COUNT(DISTINCT f.restaurant_id) > 1
) t;

SELECT r.cuisine,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(o.final_price), 2) AS revenue
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

SELECT r.restaurant_name,
       r.cuisine,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(o.final_price), 2) AS revenue
FROM (
    SELECT oi.order_id, MIN(f.restaurant_id) AS restaurant_id
    FROM orders_items oi
    JOIN food_items f ON f.item_id = oi.item_id
    GROUP BY oi.order_id
) x
JOIN orders o ON o.order_id = x.order_id
JOIN restaurants r ON r.restaurant_id = x.restaurant_id
GROUP BY r.restaurant_id, r.restaurant_name, r.cuisine
ORDER BY revenue DESC
LIMIT 8;

SELECT r.cuisine,
       COUNT(f.item_id) AS dishes,
       COUNT(DISTINCT r.restaurant_id) AS restaurants
FROM restaurants r
LEFT JOIN food_items f ON f.restaurant_id = r.restaurant_id
GROUP BY r.cuisine
ORDER BY dishes DESC;

-- 3. Dishes
SELECT f.item_name,
       SUM(oi.quantity) AS qty,
       COUNT(DISTINCT oi.order_id) AS orders
FROM orders_items oi
JOIN food_items f ON f.item_id = oi.item_id
GROUP BY f.item_name
ORDER BY qty DESC
LIMIT 10;

SELECT f.item_name,
       r.restaurant_name,
       r.cuisine,
       SUM(oi.quantity) AS qty
FROM orders_items oi
JOIN food_items f ON f.item_id = oi.item_id
JOIN restaurants r ON r.restaurant_id = f.restaurant_id
GROUP BY f.item_id, f.item_name, r.restaurant_name, r.cuisine
ORDER BY qty DESC
LIMIT 8;

SELECT COUNT(*) AS menu_rows, COUNT(DISTINCT item_name) AS distinct_names
FROM food_items;

SELECT COUNT(*) AS dishes_never_ordered
FROM food_items f
LEFT JOIN orders_items oi ON oi.item_id = f.item_id
WHERE oi.item_id IS NULL;

-- 4. Drivers and delivery time
-- delivery_minutes uses order date+time to delivered date+time
SELECT COUNT(*) AS drivers FROM drivers;

SELECT COUNT(*) AS orders,
       SUM(driver_id IS NULL) AS orders_without_driver,
       COUNT(DISTINCT driver_id) AS drivers_used
FROM orders;

SELECT COUNT(*) AS timed_orders,
       ROUND(AVG(delivery_minutes), 1) AS avg_minutes,
       MIN(delivery_minutes) AS min_minutes,
       MAX(delivery_minutes) AS max_minutes,
       SUM(delivery_minutes < 30) AS under_30,
       SUM(delivery_minutes BETWEEN 30 AND 44) AS from_30_to_44,
       SUM(delivery_minutes >= 45) AS from_45_up
FROM (
    SELECT TIMESTAMPDIFF(
        MINUTE,
        TIMESTAMP(DATE(order_date), order_time),
        TIMESTAMP(STR_TO_DATE(delivered_date, '%Y-%m-%d'), delivered_time)
    ) AS delivery_minutes
    FROM orders
) d
WHERE delivery_minutes IS NOT NULL
  AND delivery_minutes >= 0;

SELECT d.driver_id,
       d.name,
       COUNT(*) AS orders,
       ROUND(AVG(o.order_rating), 2) AS avg_order_rating
FROM orders o
JOIN drivers d ON d.driver_id = o.driver_id
GROUP BY d.driver_id, d.name
HAVING COUNT(*) >= 30
ORDER BY avg_order_rating DESC
LIMIT 5;

-- 5. Revenue, discount, delivery fee
-- final_price = total_price + delivery_fee - discount
SELECT SUM(ABS(final_price - (total_price + delivery_fee - discount)) > 0.05) AS orders_off_formula,
       ROUND(SUM(total_price), 2) AS food_total,
       ROUND(SUM(delivery_fee), 2) AS delivery_fees,
       ROUND(SUM(discount), 2) AS discounts,
       ROUND(SUM(final_price), 2) AS final_revenue
FROM orders;

SELECT DATE_FORMAT(order_date, '%Y-%m') AS month,
       COUNT(*) AS orders,
       ROUND(SUM(total_price), 2) AS food_total,
       ROUND(SUM(delivery_fee), 2) AS delivery_fees,
       ROUND(SUM(discount), 2) AS discounts,
       ROUND(SUM(final_price), 2) AS final_revenue,
       ROUND(AVG(final_price), 2) AS avg_order
FROM orders
GROUP BY DATE_FORMAT(order_date, '%Y-%m')
ORDER BY month;

SELECT SUM(discount = 0) AS no_discount_orders,
       SUM(discount > 0) AS discounted_orders,
       ROUND(AVG(CASE WHEN discount > 0 THEN discount END), 2) AS avg_discount_when_used,
       ROUND(SUM(discount) / SUM(total_price) * 100, 2) AS discount_pct_of_food
FROM orders;

SELECT CASE WHEN DAYOFWEEK(order_date) IN (1, 7) THEN 'weekend' ELSE 'weekday' END AS day_type,
       COUNT(*) AS orders,
       ROUND(SUM(final_price), 2) AS revenue,
       ROUND(AVG(final_price), 2) AS avg_order
FROM orders
GROUP BY day_type;
