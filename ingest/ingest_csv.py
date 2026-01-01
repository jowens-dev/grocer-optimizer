if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest CSVs into SQLite DB")
    parser.add_argument("--dir", required=True, help="Path to directory containing store CSVs")
    args = parser.parse_args()

    from utils.db_helpers import init_db
    import os
    import sqlite3

    # Initialize DB and schema
    init_db()

    # Connect to the DB
    from utils.db_helpers import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for csv_file in os.listdir(args.dir):
        if not csv_file.endswith(".csv"):
            continue
        
        store_key = csv_file.split("_")[0].lower()
        store_name = csv_file.split("_")[0].capitalize()
        
        print(f"Ingesting {os.path.join(args.dir, csv_file)} for {store_name}")

        cur.execute("""INSERT OR IGNORE INTO stores (store_key, store_name) VALUES (?, ?)""", (store_key, store_name))
        cur.execute("SELECT id FROM stores WHERE store_key = ?", (store_key,))
        store_id = cur.fetchone()[0]

        import csv
        with open(os.path.join(args.dir, csv_file), newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cur.execute("""
                    INSERT INTO prices (store_id, raw_name, price, unit, date_collected, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (store_id, row["raw_name"], row["price"], row["unit"], row["date_collected"], row["source"]))

    conn.commit()
    conn.close()
    print("Done.")











