ALTER TABLE products
    ADD COLUMN category VARCHAR(100) DEFAULT 'Uncategorized';

UPDATE products
SET category = 'Uncategorized'
WHERE category IS NULL;

ALTER TABLE products
    ALTER COLUMN category SET NOT NULL,
    ALTER COLUMN category DROP DEFAULT;

UPDATE products
SET stock = 0
WHERE stock IS NULL;

ALTER TABLE products
    ALTER COLUMN stock SET DEFAULT 0,
    ALTER COLUMN stock SET NOT NULL;

ALTER TABLE products
    ADD CONSTRAINT ck_products_price_positive CHECK (price > 0),
    ADD CONSTRAINT ck_products_stock_nonnegative CHECK (stock >= 0);

CREATE INDEX ix_products_category_available
    ON products (category, is_available);
CREATE INDEX ix_products_vendor_created_at
    ON products (vendor_id, created_at DESC);
