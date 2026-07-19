import sys
import os
import sqlite3
from pathlib import Path

# Resolve import paths
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db_helpers import DB_PATH, init_db

# Common items list
PRODUCTS = [
    ("milk", "Dairy"),
    ("eggs", "Dairy"),
    ("banana", "Produce"),
    ("bread", "Bakery"),
    ("chicken", "Meats"),
    ("beef", "Meats"),
    ("avocado", "Produce"),
    ("apple", "Produce"),
    ("cheese", "Dairy"),
    ("coffee", "Pantry"),
]

STORES = [
    ("Walmart", 0),
    ("Target", 0),
    ("Kroger", 0),
    ("Safeway", 0),
    ("Costco", 1),
    ("Sams Club", 1),
]

# (ProductName, StoreName, RawName, Price, Unit, Qty, DateCollected)
PRICING_DATA = [
    # Milk
    ("milk", "Walmart", "Great Value Whole Milk 1 Gal", 3.49, "gallon", 1.0, "2026-07-18"),
    ("milk", "Target", "Good & Gather Whole Milk 1 Gal", 3.69, "gallon", 1.0, "2026-07-18"),
    ("milk", "Kroger", "Kroger Brand Whole Milk 1 Gal", 3.29, "gallon", 1.0, "2026-07-18"),
    ("milk", "Safeway", "Lucerne Whole Milk 1 Gal", 3.99, "gallon", 1.0, "2026-07-18"),
    ("milk", "Costco", "Kirkland Signature Whole Milk 2-pack (2 Gal)", 5.20, "gallon", 2.0, "2026-07-18"),
    ("milk", "Sams Club", "Member's Mark Whole Milk 2-pack (2 Gal)", 5.10, "gallon", 2.0, "2026-07-18"),

    # Eggs
    ("eggs", "Walmart", "Great Value Large Grade A Eggs 12ct", 2.99, "eggs", 12.0, "2026-07-18"),
    ("eggs", "Target", "Good & Gather Large Grade A Eggs 12ct", 2.79, "eggs", 12.0, "2026-07-18"),
    ("eggs", "Kroger", "Kroger Large White Eggs 12ct", 3.19, "eggs", 12.0, "2026-07-18"),
    ("eggs", "Safeway", "Lucerne Large Grade AA Eggs 12ct", 3.49, "eggs", 12.0, "2026-07-18"),
    ("eggs", "Costco", "Kirkland Signature Large Eggs 36ct", 5.40, "eggs", 36.0, "2026-07-18"),
    ("eggs", "Sams Club", "Member's Mark Large White Eggs 36ct", 5.20, "eggs", 36.0, "2026-07-18"),

    # Banana
    ("banana", "Walmart", "Fresh Organic Bananas (per lb)", 0.59, "lb", 1.0, "2026-07-18"),
    ("banana", "Target", "Organic Bananas (per lb)", 0.49, "lb", 1.0, "2026-07-18"),
    ("banana", "Kroger", "Organic Yellow Bananas (per lb)", 0.69, "lb", 1.0, "2026-07-18"),
    ("banana", "Safeway", "Organic Bananas (per lb)", 0.79, "lb", 1.0, "2026-07-18"),
    ("banana", "Costco", "Organic Bananas 3lb Bag", 1.47, "lb", 3.0, "2026-07-18"),
    ("banana", "Sams Club", "Yellow Bananas 3lb Bag", 1.38, "lb", 3.0, "2026-07-18"),

    # Bread
    ("bread", "Walmart", "Great Value White Bread 20oz", 1.48, "lb", 1.25, "2026-07-18"),
    ("bread", "Target", "Good & Gather White Sliced Bread 20oz", 1.59, "lb", 1.25, "2026-07-18"),
    ("bread", "Kroger", "Kroger Split Top White Bread 20oz", 1.39, "lb", 1.25, "2026-07-18"),
    ("bread", "Safeway", "Safeway Signature Select Bread 20oz", 1.99, "lb", 1.25, "2026-07-18"),
    ("bread", "Costco", "Oroweat Country Buttermilk Bread 2-pack (48oz total)", 4.20, "lb", 3.0, "2026-07-18"),
    ("bread", "Sams Club", "Member's Mark White Bread 2-pack (40oz total)", 3.48, "lb", 2.5, "2026-07-18"),

    # Chicken
    ("chicken", "Walmart", "Fresh Boneless Chicken Breast (per lb)", 2.98, "lb", 1.0, "2026-07-18"),
    ("chicken", "Target", "Good & Gather Chicken Breast (per lb)", 3.49, "lb", 1.0, "2026-07-18"),
    ("chicken", "Kroger", "Heritage Farms Chicken Breast (per lb)", 2.89, "lb", 1.0, "2026-07-18"),
    ("chicken", "Safeway", "Safeway Farms Chicken Breast (per lb)", 3.99, "lb", 1.0, "2026-07-18"),
    ("chicken", "Costco", "Kirkland Signature Boneless Chicken Breast 10lb Case", 19.90, "lb", 10.0, "2026-07-18"),
    ("chicken", "Sams Club", "Member's Mark Chicken Breast 10lb Case", 18.90, "lb", 10.0, "2026-07-18"),

    # Beef
    ("beef", "Walmart", "All Natural 80/20 Ground Beef (per lb)", 4.48, "lb", 1.0, "2026-07-18"),
    ("beef", "Target", "Good & Gather Ground Beef 80/20 (per lb)", 4.99, "lb", 1.0, "2026-07-18"),
    ("beef", "Kroger", "Kroger Ground Beef 80/20 (per lb)", 4.29, "lb", 1.0, "2026-07-18"),
    ("beef", "Safeway", "Signature Select Ground Beef 80/20 (per lb)", 5.49, "lb", 1.0, "2026-07-18"),
    ("beef", "Costco", "Kirkland Signature Ground Beef Chub 80/20 6lb Pack", 20.94, "lb", 6.0, "2026-07-18"),
    ("beef", "Sams Club", "Member's Mark Ground Beef Chub 80/20 6lb Pack", 19.80, "lb", 6.0, "2026-07-18"),

    # Avocado
    ("avocado", "Walmart", "Fresh Hass Avocados (each)", 0.88, "each", 1.0, "2026-07-18"),
    ("avocado", "Target", "Hass Avocados (each)", 0.99, "each", 1.0, "2026-07-18"),
    ("avocado", "Kroger", "Medium Hass Avocados (each)", 0.89, "each", 1.0, "2026-07-18"),
    ("avocado", "Safeway", "Fresh Hass Avocados (each)", 1.25, "each", 1.0, "2026-07-18"),
    ("avocado", "Costco", "Hass Avocados 6ct Bag", 3.99, "each", 6.0, "2026-07-18"),
    ("avocado", "Sams Club", "Hass Avocados 6ct Bag", 3.78, "each", 6.0, "2026-07-18"),

    # Apple
    ("apple", "Walmart", "Gala Apples (per lb)", 1.68, "lb", 1.0, "2026-07-18"),
    ("apple", "Target", "Gala Apples 3lb Bag", 3.99, "lb", 3.0, "2026-07-18"),
    ("apple", "Kroger", "Fresh Gala Apples (per lb)", 1.59, "lb", 1.0, "2026-07-18"),
    ("apple", "Safeway", "Signature Farms Gala Apples (per lb)", 1.99, "lb", 1.0, "2026-07-18"),
    ("apple", "Costco", "Gala Apples 5lb Box", 5.95, "lb", 5.0, "2026-07-18"),
    ("apple", "Sams Club", "Gala Apples 5lb Box", 5.75, "lb", 5.0, "2026-07-18"),

    # Cheese
    ("cheese", "Walmart", "Great Value Mild Cheddar Cheese Block 8oz", 2.24, "oz", 8.0, "2026-07-18"),
    ("cheese", "Target", "Good & Gather Cheddar Cheese 8oz", 2.49, "oz", 8.0, "2026-07-18"),
    ("cheese", "Kroger", "Kroger Mild Cheddar Cheese Block 8oz", 2.19, "oz", 8.0, "2026-07-18"),
    ("cheese", "Safeway", "Lucerne Cheddar Cheese Block 8oz", 2.99, "oz", 8.0, "2026-07-18"),
    ("cheese", "Costco", "Kirkland Signature Cheddar Cheese Block 32oz (2lb)", 5.99, "oz", 32.0, "2026-07-18"),
    ("cheese", "Sams Club", "Member's Mark Cheddar Cheese Block 32oz (2lb)", 5.78, "oz", 32.0, "2026-07-18"),

    # Coffee
    ("coffee", "Walmart", "Folgers Classic Roast Ground Coffee 30.5oz", 8.48, "oz", 30.5, "2026-07-18"),
    ("coffee", "Target", "Market Pantry Medium Roast Ground Coffee 30.5oz", 7.99, "oz", 30.5, "2026-07-18"),
    ("coffee", "Kroger", "Kroger Classic Roast Ground Coffee 30.5oz", 8.19, "oz", 30.5, "2026-07-18"),
    ("coffee", "Safeway", "Signature Select Classic Roast Coffee 30.5oz", 9.49, "oz", 30.5, "2026-07-18"),
    ("coffee", "Costco", "Kirkland Signature House Blend Coffee 40oz (2.5lb)", 9.99, "oz", 40.0, "2026-07-18"),
    ("coffee", "Sams Club", "Member's Mark House Blend Coffee 40oz (2.5lb)", 9.48, "oz", 40.0, "2026-07-18"),
]

def main():
    print(f"Opening database: {DB_PATH}")
    # Always run schema to ensure users table exists
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Populate stores
    print("Seeding stores...")
    for store_name, is_club in STORES:
        cur.execute("""
            INSERT OR IGNORE INTO stores (store_name, is_club, created_at, updated_at)
            VALUES (?, ?, datetime('now'), datetime('now'))
        """, (store_name, is_club))
        cur.execute("""
            UPDATE stores SET is_club = ?, updated_at = datetime('now') WHERE store_name = ?
        """, (is_club, store_name))
        
    # 2. Populate products
    print("Seeding products...")
    for canonical_name, _ in PRODUCTS:
        cur.execute("""
            INSERT OR IGNORE INTO products (canonical_name, created_at, updated_at)
            VALUES (?, datetime('now'), datetime('now'))
        """, (canonical_name,))
        
    # 3. Populate product variants & prices
    print("Seeding prices & variants...")
    price_count = 0
    for prod_name, store_name, raw_name, price, unit, qty, date_col in PRICING_DATA:
        # Get store id
        cur.execute("SELECT id FROM stores WHERE store_name = ?", (store_name,))
        store_id = cur.fetchone()[0]
        
        # Get product id
        cur.execute("SELECT id FROM products WHERE canonical_name = ?", (prod_name,))
        product_id = cur.fetchone()[0]
        
        # Get or create product variant
        cur.execute("""
            SELECT id FROM product_variants WHERE product_id = ? AND raw_name = ?
        """, (product_id, raw_name))
        row = cur.fetchone()
        if row:
            variant_id = row[0]
        else:
            cur.execute("""
                INSERT INTO product_variants (product_id, raw_name, unit, confidence_score, status, created_at, updated_at)
                VALUES (?, ?, ?, 1.0, 'active', datetime('now'), datetime('now'))
            """, (product_id, raw_name, unit))
            variant_id = cur.lastrowid
            
        # Calculate unit price
        unit_price = price / qty if qty > 0 else None
        
        # Insert or replace price record to keep it fresh
        cur.execute("""
            INSERT OR REPLACE INTO prices (store_id, product_variant_id, price, unit_price, date_collected)
            VALUES (?, ?, ?, ?, ?)
        """, (store_id, variant_id, price, unit_price, date_col))
        price_count += 1
        
    conn.commit()
    conn.close()
    print(f"✓ Seeding complete! Populated 6 stores, 10 products, and {price_count} price entries.")

if __name__ == "__main__":
    main()
