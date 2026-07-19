# ingest_csv.py
import argparse
import os
import sqlite3
import csv
from utils.db_helpers import init_db, DB_PATH
from utils.normalize import canonicalize, parse_unit_and_qty


def get_or_create_product(cur, canonical_name):
    """Get existing product or create new one."""
    cur.execute("SELECT id FROM products WHERE canonical_name = ?", (canonical_name,))
    result = cur.fetchone()
    if result:
        return result[0]

    cur.execute("""
        INSERT INTO products (canonical_name, created_at, updated_at)
        VALUES (?, datetime('now'), datetime('now'))
    """, (canonical_name,))
    return cur.lastrowid


def get_or_create_variant(cur, product_id, raw_name, unit, confidence_score):
    """Get existing variant or create new one."""
    cur.execute("""
        SELECT id FROM product_variants
        WHERE product_id = ? AND raw_name = ?
    """, (product_id, raw_name))
    result = cur.fetchone()
    if result:
        return result[0]

    cur.execute("""
        INSERT INTO product_variants
        (product_id, raw_name, unit, confidence_score, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', datetime('now'), datetime('now'))
    """, (product_id, raw_name, unit, confidence_score))
    return cur.lastrowid


def calculate_unit_price(price, unit, quantity):
    """Calculate price per normalized unit."""
    if quantity > 0:
        return price / quantity
    return None


def ingest_csv_file(csv_path, conn):
    """Ingest a single CSV file into the database."""
    cur = conn.cursor()

    # Extract store info from filename (e.g., "walmart_2025-11-11.csv")
    filename = os.path.basename(csv_path)
    store_name = filename.split("_")[0].capitalize()

    print(f"Ingesting {csv_path} for {store_name}")

    # Identify club stores (Costco, Sam's Club, BJ's, etc.)
    is_club = 1 if store_name.lower() in {"costco", "sam's club", "sams club", "bj's", "bjs"} else 0

    # Get or create store
    cur.execute("""
        INSERT OR IGNORE INTO stores (store_name, is_club, created_at, updated_at)
        VALUES (?, ?, datetime('now'), datetime('now'))
    """, (store_name, is_club))
    # Ensure is_club is updated if store was already created
    cur.execute("""
        UPDATE stores SET is_club = ?, updated_at = datetime('now') WHERE store_name = ?
    """, (is_club, store_name))
    cur.execute("SELECT id FROM stores WHERE store_name = ?", (store_name,))
    store_id = cur.fetchone()[0]

    # Process CSV rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row_count = 0

        for row in reader:
            raw_name = row["raw_name"]
            price = float(row["price"])
            date_collected = row["date_collected"]

            # Normalize the product name
            canonical_name, confidence_score = canonicalize(raw_name)

            # Parse unit and quantity
            unit, quantity = parse_unit_and_qty(raw_name)

            # Calculate unit price if possible
            unit_price = calculate_unit_price(price, unit, quantity)

            # Get or create product
            product_id = get_or_create_product(cur, canonical_name)

            # Get or create product variant
            variant_id = get_or_create_variant(cur, product_id, raw_name, unit, confidence_score)

            # Insert price record
            cur.execute("""
                INSERT INTO prices (
                    store_id, product_variant_id, price, unit_price, date_collected
                )
                VALUES (?, ?, ?, ?, ?)
            """, (store_id, variant_id, price, unit_price, date_collected))

            row_count += 1

        print(f"  ✓ Processed {row_count} products")

    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Ingest store CSV files into SQLite database")
    parser.add_argument("--dir", required=True, help="Path to directory containing store CSVs")
    parser.add_argument("--file", help="Path to single CSV file (alternative to --dir)")
    args = parser.parse_args()

    # Initialize database and schema
    print("Initializing database...")
    init_db()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    try:
        if args.file:
            # Ingest single file
            ingest_csv_file(args.file, conn)
        else:
            # Ingest all CSV files in directory
            csv_files = [f for f in os.listdir(args.dir) if f.endswith(".csv")]
            print(f"Found {len(csv_files)} CSV files to process")

            for csv_file in csv_files:
                csv_path = os.path.join(args.dir, csv_file)
                ingest_csv_file(csv_path, conn)
                print()

        print("✓ Ingestion complete!")

        # Print summary statistics
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        product_count = cur.fetchone()  # ← Added  here
        cur.execute("SELECT COUNT(*) FROM product_variants")
        variant_count = cur.fetchone()  # ← Added  here
        cur.execute("SELECT COUNT(*) FROM prices")
        price_count = cur.fetchone()  # ← Added  here

        print(f"Database Summary:")
        print(f"  - Products: {product_count}")
        print(f"  - Product Variants: {variant_count}")
        print(f"  - Price Records: {price_count}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
