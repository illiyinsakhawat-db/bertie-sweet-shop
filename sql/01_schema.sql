-- =====================================================================
--  Bertie Sweet Online Shop  |  01_schema.sql
--  PostgreSQL 14+ | Normalised to Third Normal Form (3NF)
--
--  Run order:
--    01_schema.sql  -> 02_seed_data.sql -> 03_views.sql -> 04_analysis_queries.sql
-- =====================================================================

DROP SCHEMA IF EXISTS bertie CASCADE;
CREATE SCHEMA bertie;
SET search_path TO bertie;

-- ---------------------------------------------------------------------
-- 1. Logistics: Region -> Warehouse -> Distribution Centre
-- ---------------------------------------------------------------------
CREATE TABLE region (
    region_id    SMALLSERIAL PRIMARY KEY,
    region_name  VARCHAR(60) NOT NULL UNIQUE
);

-- One warehouse per region (1..1 in the ERD) -> enforced with UNIQUE
CREATE TABLE warehouse (
    warehouse_id        SMALLSERIAL PRIMARY KEY,
    region_id           SMALLINT    NOT NULL UNIQUE REFERENCES region(region_id),
    warehouse_name      VARCHAR(80) NOT NULL,
    warehouse_address   VARCHAR(150) NOT NULL,
    warehouse_telephone VARCHAR(20),
    warehouse_postcode  VARCHAR(10) NOT NULL
);

-- Region is reachable through warehouse, so it is NOT repeated here (3NF)
CREATE TABLE distribution_centre (
    dc_id         SMALLSERIAL PRIMARY KEY,
    warehouse_id  SMALLINT    NOT NULL REFERENCES warehouse(warehouse_id),
    dc_name       VARCHAR(80) NOT NULL,
    dc_address    VARCHAR(150) NOT NULL,
    dc_telephone  VARCHAR(20),
    dc_postcode   VARCHAR(10) NOT NULL
);

-- ---------------------------------------------------------------------
-- 2. Product catalogue
-- ---------------------------------------------------------------------
CREATE TABLE sweet_category (
    category_id    SMALLSERIAL PRIMARY KEY,
    category_name  VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE sweet (
    sweet_code        VARCHAR(10)  PRIMARY KEY,           -- e.g. 'SW001'
    sweet_name        VARCHAR(80)  NOT NULL,
    sweet_description TEXT,
    size_grams        SMALLINT     NOT NULL CHECK (size_grams > 0),
    unit_price        NUMERIC(6,2) NOT NULL CHECK (unit_price > 0),
    category_id       SMALLINT     NOT NULL REFERENCES sweet_category(category_id),
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE
);

-- A multi-pack bundles 2+ sweets (Sweet 2..* -> Sweet_Packaging in the ERD)
CREATE TABLE multi_pack (
    multi_pack_id     SMALLSERIAL  PRIMARY KEY,
    multi_pack_name   VARCHAR(80)  NOT NULL,
    multi_pack_description TEXT,
    multi_pack_price  NUMERIC(6,2) NOT NULL CHECK (multi_pack_price > 0)
);

-- Junction table (ERD: Sweet_Packaging)
CREATE TABLE multi_pack_item (
    multi_pack_id  SMALLINT    NOT NULL REFERENCES multi_pack(multi_pack_id) ON DELETE CASCADE,
    sweet_code     VARCHAR(10) NOT NULL REFERENCES sweet(sweet_code),
    quantity       SMALLINT    NOT NULL DEFAULT 1 CHECK (quantity > 0),
    PRIMARY KEY (multi_pack_id, sweet_code)
);

CREATE TABLE offer (
    offer_id      SMALLSERIAL  PRIMARY KEY,
    offer_name    VARCHAR(80)  NOT NULL,
    discount_pct  NUMERIC(5,2) NOT NULL CHECK (discount_pct > 0 AND discount_pct < 100)
);

-- Junction table (ERD: Sweet_offers) - many sweets <-> many offers, time-boxed
CREATE TABLE sweet_offer (
    sweet_code        VARCHAR(10) NOT NULL REFERENCES sweet(sweet_code),
    offer_id          SMALLINT    NOT NULL REFERENCES offer(offer_id),
    offer_start_date  DATE        NOT NULL,
    offer_end_date    DATE        NOT NULL,
    PRIMARY KEY (sweet_code, offer_id, offer_start_date),
    CHECK (offer_end_date >= offer_start_date)
);

-- Stock is held per distribution centre per sweet
-- (replaces sweet_available_quantity / stock_availability on Sweet & Multi-Pack)
CREATE TABLE stock (
    dc_id              SMALLINT    NOT NULL REFERENCES distribution_centre(dc_id),
    sweet_code         VARCHAR(10) NOT NULL REFERENCES sweet(sweet_code),
    quantity_on_hand   INTEGER     NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_level      INTEGER     NOT NULL DEFAULT 50 CHECK (reorder_level >= 0),
    PRIMARY KEY (dc_id, sweet_code)
);

-- ---------------------------------------------------------------------
-- 3. Customers
-- ---------------------------------------------------------------------
CREATE TABLE customer (
    customer_id    SERIAL       PRIMARY KEY,               -- surrogate key (ERD used name as PK)
    username       VARCHAR(40)  NOT NULL UNIQUE,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    password_hash  CHAR(60)     NOT NULL,                  -- bcrypt hash, never plain text
    registered_on  DATE         NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE delivery_address (
    address_id       SERIAL       PRIMARY KEY,
    customer_id      INTEGER      NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    address_line     VARCHAR(150) NOT NULL,
    city             VARCHAR(60)  NOT NULL,
    postcode         VARCHAR(10)  NOT NULL,
    region_id        SMALLINT     NOT NULL REFERENCES region(region_id),
    is_default       BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Full card numbers are never stored (PCI-DSS); only a token + last 4 digits
CREATE TABLE payment_method (
    payment_method_id  SERIAL      PRIMARY KEY,
    customer_id        INTEGER     NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    card_type          VARCHAR(20) NOT NULL CHECK (card_type IN ('Visa','Mastercard','Amex','PayPal')),
    card_last4         CHAR(4),
    payment_token      VARCHAR(64) NOT NULL UNIQUE,
    payment_description VARCHAR(100)
);

-- ---------------------------------------------------------------------
-- 4. Shopping list & basket (pre-purchase)
--    A line is EITHER a single sweet OR a multi-pack (exactly one)
-- ---------------------------------------------------------------------
CREATE TABLE shopping_list (
    shopping_list_id  SERIAL      PRIMARY KEY,
    customer_id       INTEGER     NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    list_name         VARCHAR(60) NOT NULL,
    created_on        DATE        NOT NULL DEFAULT CURRENT_DATE,
    expires_on        DATE,
    CHECK (expires_on IS NULL OR expires_on >= created_on)
);

CREATE TABLE shopping_list_item (
    list_item_id      SERIAL      PRIMARY KEY,
    shopping_list_id  INTEGER     NOT NULL REFERENCES shopping_list(shopping_list_id) ON DELETE CASCADE,
    sweet_code        VARCHAR(10) REFERENCES sweet(sweet_code),
    multi_pack_id     SMALLINT    REFERENCES multi_pack(multi_pack_id),
    quantity          SMALLINT    NOT NULL DEFAULT 1 CHECK (quantity > 0),
    CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)
);

CREATE TABLE shopping_basket (
    basket_id    SERIAL      PRIMARY KEY,
    customer_id  INTEGER     NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    created_at   TIMESTAMP   NOT NULL DEFAULT now(),
    status       VARCHAR(12) NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open','checked_out','abandoned'))
);

CREATE TABLE basket_item (
    basket_item_id  SERIAL      PRIMARY KEY,
    basket_id       INTEGER     NOT NULL REFERENCES shopping_basket(basket_id) ON DELETE CASCADE,
    sweet_code      VARCHAR(10) REFERENCES sweet(sweet_code),
    multi_pack_id   SMALLINT    REFERENCES multi_pack(multi_pack_id),
    quantity        SMALLINT    NOT NULL DEFAULT 1 CHECK (quantity > 0),
    CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)
);

-- ---------------------------------------------------------------------
-- 5. Orders (standard online orders)
--    Totals are NOT stored - they are derived in views (avoids update anomalies).
--    unit_price IS stored on the line: it is the price *at time of sale*,
--    a historical fact, not a copy of sweet.unit_price.
-- ---------------------------------------------------------------------
CREATE TABLE customer_order (
    order_id            SERIAL       PRIMARY KEY,
    customer_id         INTEGER      NOT NULL REFERENCES customer(customer_id),
    basket_id           INTEGER      UNIQUE REFERENCES shopping_basket(basket_id),
    dc_id               SMALLINT     NOT NULL REFERENCES distribution_centre(dc_id),
    address_id          INTEGER      NOT NULL REFERENCES delivery_address(address_id),
    payment_method_id   INTEGER      NOT NULL REFERENCES payment_method(payment_method_id),
    order_date          DATE         NOT NULL,
    delivery_date       DATE,
    delivery_charge     NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (delivery_charge >= 0),
    order_status        VARCHAR(12)  NOT NULL DEFAULT 'placed'
                        CHECK (order_status IN ('placed','dispatched','delivered','cancelled')),
    CHECK (delivery_date IS NULL OR delivery_date >= order_date)
);

CREATE TABLE order_item (
    order_item_id   SERIAL       PRIMARY KEY,
    order_id        INTEGER      NOT NULL REFERENCES customer_order(order_id) ON DELETE CASCADE,
    sweet_code      VARCHAR(10)  REFERENCES sweet(sweet_code),
    multi_pack_id   SMALLINT     REFERENCES multi_pack(multi_pack_id),
    quantity        SMALLINT     NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(6,2) NOT NULL CHECK (unit_price >= 0),
    discount_pct    NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct < 100),
    CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)
);

-- ---------------------------------------------------------------------
-- 6. Special orders (one-off bulk orders) & Standing orders (recurring)
-- ---------------------------------------------------------------------
CREATE TABLE special_order (
    special_order_id  SERIAL   PRIMARY KEY,
    customer_id       INTEGER  NOT NULL REFERENCES customer(customer_id),
    dc_id             SMALLINT NOT NULL REFERENCES distribution_centre(dc_id),
    order_date        DATE     NOT NULL,
    delivery_date     DATE     NOT NULL,
    CHECK (delivery_date >= order_date)
);

CREATE TABLE special_order_item (
    special_order_item_id SERIAL     PRIMARY KEY,
    special_order_id  INTEGER     NOT NULL REFERENCES special_order(special_order_id) ON DELETE CASCADE,
    sweet_code        VARCHAR(10) REFERENCES sweet(sweet_code),
    multi_pack_id     SMALLINT    REFERENCES multi_pack(multi_pack_id),
    quantity          INTEGER     NOT NULL CHECK (quantity > 0),
    unit_price        NUMERIC(6,2) NOT NULL CHECK (unit_price >= 0),
    CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)
);

CREATE TABLE standing_order (
    standing_order_id  SERIAL      PRIMARY KEY,
    customer_id        INTEGER     NOT NULL REFERENCES customer(customer_id),
    dc_id              SMALLINT    NOT NULL REFERENCES distribution_centre(dc_id),
    start_date         DATE        NOT NULL,
    frequency          VARCHAR(12) NOT NULL CHECK (frequency IN ('weekly','fortnightly','monthly')),
    delivery_day       VARCHAR(9)  NOT NULL CHECK (delivery_day IN
                       ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')),
    revised_date       DATE,
    is_active          BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE standing_order_item (
    standing_order_item_id SERIAL  PRIMARY KEY,
    standing_order_id  INTEGER     NOT NULL REFERENCES standing_order(standing_order_id) ON DELETE CASCADE,
    sweet_code         VARCHAR(10) REFERENCES sweet(sweet_code),
    multi_pack_id      SMALLINT    REFERENCES multi_pack(multi_pack_id),
    quantity           SMALLINT    NOT NULL CHECK (quantity > 0),
    CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)
);

-- ---------------------------------------------------------------------
-- 7. Indexes on foreign keys & common filter columns
-- ---------------------------------------------------------------------
CREATE INDEX idx_dc_warehouse        ON distribution_centre(warehouse_id);
CREATE INDEX idx_sweet_category      ON sweet(category_id);
CREATE INDEX idx_stock_sweet         ON stock(sweet_code);
CREATE INDEX idx_address_customer    ON delivery_address(customer_id);
CREATE INDEX idx_payment_customer    ON payment_method(customer_id);
CREATE INDEX idx_order_customer      ON customer_order(customer_id);
CREATE INDEX idx_order_date          ON customer_order(order_date);
CREATE INDEX idx_order_dc            ON customer_order(dc_id);
CREATE INDEX idx_order_item_order    ON order_item(order_id);
CREATE INDEX idx_order_item_sweet    ON order_item(sweet_code);
CREATE INDEX idx_order_item_pack     ON order_item(multi_pack_id);
CREATE INDEX idx_sweet_offer_dates   ON sweet_offer(offer_start_date, offer_end_date);
