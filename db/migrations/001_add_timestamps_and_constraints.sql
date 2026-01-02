-- Migration 001: Add timestamps and additional constraints
-- Date: 2026-01-01
-- Description: Adds audit timestamps, confidence scoring, and unique constraints

-- Add timestamps to stores (using NULL as default since datetime('now') is not constant)
ALTER TABLE stores ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE stores ADD COLUMN updated_at TEXT DEFAULT NULL;

-- Add timestamps to products
ALTER TABLE products ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE products ADD COLUMN updated_at TEXT DEFAULT NULL;

-- Add timestamps to product_variants
ALTER TABLE product_variants ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE product_variants ADD COLUMN updated_at TEXT DEFAULT NULL;

-- Add confidence and status to product_variants
ALTER TABLE product_variants ADD COLUMN confidence_score REAL DEFAULT 1.0;
ALTER TABLE product_variants ADD COLUMN status TEXT DEFAULT 'active';

-- Add unique constraint to prevent duplicate prices
CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_unique
ON prices(store_id, product_variant_id, date_collected);

-- Update existing rows to set current timestamp (optional)
UPDATE stores SET created_at = datetime('now'), updated_at = datetime('now') WHERE created_at IS NULL;
UPDATE products SET created_at = datetime('now'), updated_at = datetime('now') WHERE created_at IS NULL;
UPDATE product_variants SET created_at = datetime('now'), updated_at = datetime('now') WHERE created_at IS NULL;
-- Migration 001: Add timestamps and additional constraints
-- Date: 2026-01-01
-- Description: Adds audit timestamps, confidence scoring, and unique constraints

-- Add timestamps to stores
ALTER TABLE stores ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE stores ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- Add timestamps to products
ALTER TABLE products ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE products ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- Add timestamps to product_variants
ALTER TABLE product_variants ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE product_variants ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- Add confidence and status to product_variants
ALTER TABLE product_variants ADD COLUMN confidence_score REAL DEFAULT 1.0;
ALTER TABLE product_variants ADD COLUMN status TEXT DEFAULT 'active';

-- Add unique constraint to prevent duplicate prices
CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_unique
ON prices(store_id, product_variant_id, date_collected);

