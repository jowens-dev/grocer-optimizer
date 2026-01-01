-- schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_key TEXT UNIQUE,
    store_name TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    raw_name TEXT,
    unit TEXT,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    product_variant_id INTEGER,
    raw_name TEXT,
    price REAL NOT NULL,
    unit_price REAL, -- price per normalized unit if available
    unit TEXT,
    date_collected TEXT NOT NULL, -- ISO date: YYYY-MM-DD
    source TEXT,
    FOREIGN KEY(store_id) REFERENCES stores(id),
    FOREIGN KEY(product_variant_id) REFERENCES product_variants(id)
);

CREATE INDEX IF NOT EXISTS idx_prices_product_date ON prices(product_variant_id, date_collected);
CREATE INDEX IF NOT EXISTS idx_prices_store_date ON prices(store_id, date_collected);

