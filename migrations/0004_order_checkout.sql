ALTER TABLE orders
    ADD COLUMN order_number VARCHAR(40),
    ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid';

UPDATE orders
SET order_number = 'AMI-LEGACY-' || id::text
WHERE order_number IS NULL;

UPDATE orders SET status = 'pending' WHERE status IS NULL;
UPDATE orders SET payment_method = 'cash_on_delivery' WHERE payment_method IS NULL;

ALTER TABLE orders
    ALTER COLUMN order_number SET NOT NULL,
    ALTER COLUMN status SET NOT NULL,
    ALTER COLUMN payment_method SET NOT NULL,
    ADD CONSTRAINT ck_orders_total_positive CHECK (total_amount > 0),
    ADD CONSTRAINT ck_orders_status_valid CHECK (
        status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')
    ),
    ADD CONSTRAINT ck_orders_payment_status_valid CHECK (
        payment_status IN ('unpaid', 'paid')
    ),
    ADD CONSTRAINT ck_orders_payment_method_cod CHECK (
        payment_method = 'cash_on_delivery'
    );

CREATE UNIQUE INDEX ix_orders_order_number ON orders (order_number);

ALTER TABLE order_items
    ADD COLUMN product_name VARCHAR(150);

UPDATE order_items AS item
SET product_name = product.name
FROM products AS product
WHERE item.product_id = product.id
  AND item.product_name IS NULL;

ALTER TABLE order_items
    ALTER COLUMN product_name SET NOT NULL,
    ADD CONSTRAINT ck_order_items_quantity_positive CHECK (quantity > 0),
    ADD CONSTRAINT ck_order_items_price_positive CHECK (unit_price > 0);
