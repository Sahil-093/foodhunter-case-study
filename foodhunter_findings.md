# FoodHunter case study, June to September 2022

This is a case study on the FoodHunter dataset from the Coursera course Data Analytics Using SQL. The queries and the reading of the results are mine. I did not collect the data.

The extract runs from 1 June 2022 to 29 September 2022. It holds 43,118 orders, 9,874 customers who ordered, 100 restaurants, and 250 drivers. Final revenue is 1,197,706. The average order is 27.78.

## Customers come back

Of 10,000 customers, 9,874 placed at least one order and 126 never did. 9,349 ordered more than once. Only 525 ordered once. The busiest customer placed 14 orders. The average is 4.37 orders per customer who ordered.

## Revenue fell because order volume fell

June had 12,502 orders and 347,578 in final revenue. August had 10,107 orders and 283,366. The average order stayed between 27.57 and 28.04 in every month. September ends on the 29th, and the decline is already clear from June to August.

The bill identity in this data is:

final_price = total_price + delivery_fee - discount

Food total was 1,229,527. Delivery fees were 131,859. Discounts were 163,680. Discount is 13.3 percent of the food total, and it was applied on 28,814 orders.

Weekday revenue was 870,423 across 31,412 orders (average 27.71). Weekend revenue was 327,283 across 11,706 orders (average 27.96).

## Chinese leads orders and revenue

Italian has the most restaurants (38) and the most menu dishes (104). Chinese has 29 restaurants and leads the allocated results: 15,021 orders and 437,707 in revenue. Italian follows at 13,381 orders and 356,704. Indian is 8,785 orders and 232,918. Thai is 5,931 orders and 170,377.

Across restaurants, the top dish name by quantity is Peking duck (2,851). The single menu item with the highest quantity is Shrimp fried rice at Casa Mono (341). The menu has 314 rows and 173 distinct names. 14 dishes were never ordered.

## Delivery is fast and even

Average delivery time is 23.4 minutes. The range is 10 to 41 minutes. 35,734 orders arrived in under 30 minutes, and none took 45 minutes or more. Every order has a driver, and all 250 drivers were used. Among drivers with at least 30 orders, Brandon Luft has the highest average order rating, 3.86, on 159 orders.

## How to read the numbers

A few fields need care, or the totals get misread.

- 14,300 orders contain dishes from more than one restaurant. Cuisine revenue above assigns the whole order to the smallest restaurant_id on that order.
- Some restaurant names do not match the cuisine label. Hwa Yuan Szechuan is stored as Thai.
- drivers.rating is not the average of order_rating. Four drivers have a profile rating of 5, while their order ratings sit between about 3.46 and 3.69.
- food_type uses both Veg and vegetarian, and both Non-veg and non-vegetarian.

The SQL for every figure is in foodhunter_analysis.sql.
