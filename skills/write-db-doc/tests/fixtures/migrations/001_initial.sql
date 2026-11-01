-- Synthetic shop with eight tables and relationships for rendering tests.
CREATE TABLE customer (id bigint PRIMARY KEY, name text NOT NULL);
CREATE TABLE category (id bigint PRIMARY KEY, name text NOT NULL);
CREATE TABLE product (
    id bigint PRIMARY KEY,
    category_id bigint NOT NULL REFERENCES category(id),
    name text NOT NULL
);
CREATE TABLE coupon (id bigint PRIMARY KEY, code text NOT NULL UNIQUE);
CREATE TABLE orders (
    id bigint PRIMARY KEY,
    customer_id bigint NOT NULL REFERENCES customer(id),
    coupon_id bigint
);
CREATE TABLE order_item (
    id bigint PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id),
    product_id bigint NOT NULL REFERENCES product(id),
    qty integer NOT NULL
);
CREATE TABLE payment (
    id bigint PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id),
    amount numeric(12,2) NOT NULL
);
CREATE TABLE shipment (
    id bigint PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id)
);
