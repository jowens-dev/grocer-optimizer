-- schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT NULL,
    updated_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT NULL,
    updated_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    raw_name TEXT NOT NULL,
    unit TEXT,
    confidence_score REAL DEFAULT 1.0,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT NULL,
    updated_at TEXT DEFAULT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    product_variant_id INTEGER NOT NULL,
    price REAL NOT NULL,
    unit_price REAL,
    date_collected TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (product_variant_id) REFERENCES product_variants(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_canonical ON products(canonical_name);
CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_variants_raw ON product_variants(raw_name);
CREATE INDEX IF NOT EXISTS idx_prices_store ON prices(store_id);
CREATE INDEX IF NOT EXISTS idx_prices_variant ON prices(product_variant_id);
CREATE INDEX IF NOT EXISTS idx_prices_store_date ON prices(store_id, date_collected);

-- Unique constraint to prevent duplicate prices
CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_unique
ON prices(store_id, product_variant_id, date_collected);
