ALTER TABLE order_items
    ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'pending',
    ADD CONSTRAINT ck_order_items_status_valid CHECK (
        status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')
    );
