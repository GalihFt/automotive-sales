SELECT  * FROM automotive.dealers;

SELECT * FROM automotive.sales;

-- NUMBER ONE
WITH dealer_rank AS(
    SELECT
        dls.region,
        dls.dealer_id,
        dls.dealer_name,
        COALESCE(SUM(sls.qty * sls.unit_price), 0) AS omzet,
        COALESCE(SUM(sls.qty),0) AS unit_sold,
        DENSE_RANK() OVER(ORDER BY SUM(sls.qty * sls.unit_price) DESC) AS ranking
    FROM automotive.dealers dls
    LEFT JOIN automotive.sales sls ON dls.dealer_id = sls.dealer_id
        AND sls.order_date >= '2026-01-01'
        AND sls.order_date < '2027-01-01'
        AND sls.status = 'delivered'
    GROUP BY dls.region, dls.dealer_id, dls.dealer_name
)
SELECT * FROM dealer_rank
WHERE ranking <= 3 
ORDER BY ranking ASC;

-- NUMBER TWO
SELECT * FROM automotive.sales;

WITH current_omzet AS (
    SELECT
        EXTRACT(MONTH FROM sls.order_date) AS month,
        SUM(sls.qty * sls.unit_price) AS omzet
    FROM automotive.sales sls
    WHERE sls.status = 'delivered'
        AND sls.order_date >= '2026-01-01'
        AND sls.order_date < '2027-01-01'
    GROUP BY month
    ORDER BY month ASC
), prev_revenue AS (
    SELECT
        month,
        omzet,
        LAG(omzet) OVER (
            ORDER BY month
        ) AS prev_omzet
    FROM current_omzet
)
SELECT
    month,
    omzet,
    prev_omzet,
    ROUND((((omzet - prev_omzet)/prev_omzet)*100),2)
FROM prev_revenue
ORDER BY month;

-- NUMBER THREE
WITH data_total_sold AS (
    SELECT 
        vhs.brand,
        vhs.vehicle_id,
        vhs.model,
        SUM(sls.qty) AS total_sold,
        SUM(COALESCE(SUM(sls.qty), 0)) OVER (
            PARTITION BY vhs.brand
        ) AS total_brand_sold
    FROM automotive.vehicles vhs
    LEFT JOIN automotive.sales sls ON vhs.vehicle_id = sls.vehicle_id
        AND sls.status = 'delivered'
        AND sls.order_date >= '2026-01-01'
        AND sls.order_date < '2027-01-01'
    GROUP BY vhs.brand, vhs.vehicle_id, vhs.model
)
SELECT
    brand,
    vehicle_id,
    model,
    total_sold,
    total_brand_sold,
    ROUND((total_sold/total_brand_sold),2) AS pct_contribute
FROM data_total_sold
WHERE ROUND((total_sold/total_brand_sold),2) >= 0.2
ORDER BY  brand ASC, pct_contribute DESC;

-- NUMBER FOUR
SELECT * FROM automotive.sales;
SELECT * FROM automotive.vehicles;

WITH selling_price AS (
    SELECT
        vhs.vehicle_id,
        vhs.model,
        ROUND(SUM(sls.qty * sls.unit_price) / SUM(sls.qty), 2) AS mean_selling_price,
        COUNT(vhs.vehicle_id) AS qty_sold
    FROM automotive.vehicles vhs
    LEFT JOIN automotive.sales sls ON vhs.vehicle_id = sls.vehicle_id
        AND sls.status = 'delivered'
        AND sls.order_date >= '2026-01-01'
        AND sls.order_date < '2027-01-01'
    GROUP BY vhs.vehicle_id, vhs.model
), diff_price AS(
    SELECT 
        sp.vehicle_id,
        sp.model,
        vhs.list_price,
        sp.mean_selling_price,
        (vhs.list_price - sp.mean_selling_price) AS diff_price,
        ROUND(((vhs.list_price - sp.mean_selling_price) / vhs.list_price) * 100, 2) AS pct_diff_price,
        sp.qty_sold
    FROM automotive.vehicles vhs
    LEFT JOIN selling_price sp ON vhs.vehicle_id = sp.vehicle_id
    )
SELECT 
    dp.vehicle_id,
    dp.model,
    dp.list_price,
    dp.mean_selling_price,
    dp.diff_price,
    dp.pct_diff_price,
    dp.qty_sold,
    RANK() OVER(
        ORDER BY pct_diff_price DESC,
                vehicle_id ASC
    ) AS ranking
FROM diff_price dp
WHERE dp.qty_sold >= 20;

    

