-- Dipanggil pipeline setelah sales_staging diisi pada koneksi yang sama.
-- updated_at sama/lebih lama dilewati agar impor ulang aman.
INSERT INTO automotive.sales AS target (
    order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
)
SELECT order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
FROM sales_staging
ON CONFLICT (order_id) DO UPDATE SET
    order_date = EXCLUDED.order_date,
    dealer_id = EXCLUDED.dealer_id,
    vehicle_id = EXCLUDED.vehicle_id,
    qty = EXCLUDED.qty,
    unit_price = EXCLUDED.unit_price,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at
WHERE target.updated_at IS NULL OR EXCLUDED.updated_at > target.updated_at;
