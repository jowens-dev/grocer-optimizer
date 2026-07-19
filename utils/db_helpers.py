import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "grocery.db")

def init_db():
    with open(os.path.join(os.path.dirname(__file__), "../db/schema.sql")) as f:
        schema = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.close()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Self-healing migration: check if 'is_club' exists in 'stores' table, add it if missing
    try:
        cur.execute("SELECT is_club FROM stores LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cur.execute("ALTER TABLE stores ADD COLUMN is_club INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
    # Self-healing migration: check if 'users' table exists, create it if missing
    try:
        cur.execute("SELECT id FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    tier TEXT DEFAULT 'free',
                    club_memberships TEXT DEFAULT '[]',
                    zip_code TEXT DEFAULT '90210',
                    created_at TEXT DEFAULT NULL,
                    updated_at TEXT DEFAULT NULL
                )
            """)
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
    # Self-healing migration: check if 'zip_code' exists in 'users' table, add it if missing
    try:
        cur.execute("SELECT zip_code FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN zip_code TEXT DEFAULT '90210'")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Self-healing migration: check if 'zip_code' exists in 'prices' table, add it if missing
    try:
        cur.execute("SELECT zip_code FROM prices LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cur.execute("ALTER TABLE prices ADD COLUMN zip_code TEXT DEFAULT '90210'")
            # Drop old constraint and create index including zip_code
            cur.execute("DROP INDEX IF EXISTS idx_prices_unique")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_unique ON prices(store_id, product_variant_id, zip_code, date_collected)")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
    conn.row_factory = sqlite3.Row
    return conn
