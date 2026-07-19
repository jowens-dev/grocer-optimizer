import os
os.environ["AISLEONE_ENV"] = "test"
import sqlite3
import pytest
from fastapi.testclient import TestClient
from api.app import app
from utils.db_helpers import DB_PATH

client = TestClient(app)

@pytest.fixture
def auth_headers():
    # Clean up to prevent duplicate registration
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = 'testuser'")
    conn.commit()
    conn.close()

    # Register
    register_res = client.post(
        "/auth/register",
        json={"username": "testuser", "password": "password123"}
    )
    assert register_res.status_code == 200

    # Get Token
    login_res = client.post(
        "/auth/token",
        json={"username": "testuser", "password": "password123"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    yield headers

    # Cleanup user
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = 'testuser'")
    conn.commit()
    conn.close()


def test_recipe_estimate_prioritizes_preferred_stores(auth_headers):
    # Free tier defaults to Sam, which is Single Store. Let's make sure it estimates.
    response = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "preferred_stores": ["Kroger", "Walmart"],
            "shopper_persona": "single_store_sam"
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipe_name"] == "Breakfast"
    assert payload["selected_store"] == "Kroger"
    assert payload["estimated_total"] == 3.29
    assert payload["ingredients"][0]["store"] == "Kroger"


@pytest.fixture
def setup_club_store():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("INSERT OR IGNORE INTO stores (store_name, is_club) VALUES ('Costco', 1)")
    cur.execute("SELECT id FROM stores WHERE store_name = 'Costco'")
    costco_id = cur.fetchone()[0]
    
    cur.execute("SELECT id FROM products WHERE canonical_name = 'milk'")
    milk_id = cur.fetchone()[0]
    
    cur.execute(
        "INSERT INTO product_variants (product_id, raw_name, unit, confidence_score) VALUES (?, 'Costco Milk 1 Gal', 'gallon', 1.0)",
        (milk_id,)
    )
    variant_id = cur.lastrowid
    
    # Store with zip_code partition '90210'
    cur.execute(
        "INSERT INTO prices (store_id, product_variant_id, price, zip_code, date_collected) VALUES (?, ?, 2.50, '90210', '2026-01-02 02:49:08')",
        (costco_id, variant_id)
    )
    price_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    yield
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM prices WHERE id = ?", (price_id,))
    cur.execute("DELETE FROM product_variants WHERE id = ?", (variant_id,))
    cur.execute("DELETE FROM stores WHERE id = ?", (costco_id,))
    conn.commit()
    conn.close()


def test_free_tier_ignores_club_and_forces_single_store(auth_headers, setup_club_store):
    # Free tier defaults to single_store_sam even if requesting Francine or Costco memberships
    response = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    # Mode should be forced back to single_store
    assert payload["mode"] == "single_store"
    # Costco (2.50) is ignored, so Kroger (3.29) is picked
    assert payload["estimated_total"] == 3.29
    assert payload["selected_store"] == "Kroger"


def test_premium_tier_includes_club_membership(auth_headers, setup_club_store):
    # Update user profile to premium with Costco membership
    profile_res = client.post(
        "/users/profile",
        json={"tier": "premium", "club_memberships": ["Costco"], "zip_code": "90210"},
        headers=auth_headers
    )
    assert profile_res.status_code == 200

    response = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    # Mode should be mapped to maximize_savings
    assert payload["mode"] == "maximize_savings"
    # Costco (2.50) is included and picked
    assert payload["estimated_total"] == 2.50
    assert payload["ingredients"][0]["store"] == "Costco"


def test_premium_tier_without_club_membership(auth_headers, setup_club_store):
    # Update user profile to premium but no Costco
    profile_res = client.post(
        "/users/profile",
        json={"tier": "premium", "club_memberships": [], "zip_code": "90210"},
        headers=auth_headers
    )
    assert profile_res.status_code == 200

    response = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    # Costco is filtered out, so Kroger (3.29) is picked
    assert payload["estimated_total"] == 3.29
    assert payload["ingredients"][0]["store"] == "Kroger"


def test_cheapest_list_tier_validation(auth_headers, setup_club_store):
    # Free tier request - should force single_store_sam and ignore Costco
    response = client.post(
        "/cheapest",
        json={
            "items": ["milk", "banana", "eggs"],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    # Mode should be mapped to single_store (from single_store_sam)
    assert payload["mode"] == "single_store"
    # Costco (2.50) is ignored, so Kroger or Walmart is selected
    # Walmart: milk(3.49) + banana(0.59) + eggs(2.99) = 7.07
    # Kroger: milk(3.29) + banana(0.69) + eggs(3.19) = 7.17
    # Target: milk(3.69) + banana(0.49) + eggs(2.79) = 6.97
    assert payload["selected_store"] == "Target"
    assert abs(payload["total_cost"] - 6.97) < 0.01


def test_cheapest_list_premium_francine(auth_headers, setup_club_store):
    # Update profile to premium with Costco
    profile_res = client.post(
        "/users/profile",
        json={"tier": "premium", "club_memberships": ["Costco"], "zip_code": "90210"},
        headers=auth_headers
    )
    assert profile_res.status_code == 200

    # Premium tier with Francine and Costco membership
    response = client.post(
        "/cheapest",
        json={
            "items": ["milk", "banana", "eggs"],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    assert payload["mode"] == "maximize_savings"
    # Costco (2.50) milk, Target banana (0.49), Target eggs (2.79)
    # Total: 2.50 + 0.49 + 2.79 = 5.78
    assert abs(payload["total_cost"] - 5.78) < 0.01
    
    # Verify items are mapped to best store
    items = {item["canonical"]: item["store"] for item in payload["items"]}
    assert items["milk"] == "Costco"
    assert items["banana"] == "Target"
    assert items["eggs"] == "Target"


def test_zip_code_partitioning(auth_headers):
    # Seed 10001 location in SQLite database
    from ingest.scrape_instacart import scrape_and_ingest
    scrape_and_ingest("10001")

    # Default zip code for test user is 90210. Kroger milk in 90210 is 3.29.
    response_90210 = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "shopper_persona": "single_store_sam"
        },
        headers=auth_headers
    )
    assert response_90210.status_code == 200
    res_90210 = response_90210.json()
    print("\n[DEBUG] res_90210:", res_90210)
    assert res_90210["estimated_total"] == 3.29

    # Update zip code to 10001
    profile_res = client.post(
        "/users/profile",
        json={"tier": "free", "club_memberships": [], "zip_code": "10001"},
        headers=auth_headers
    )
    assert profile_res.status_code == 200

    response_10001 = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "shopper_persona": "single_store_sam"
        },
        headers=auth_headers
    )
    assert response_10001.status_code == 200
    res_10001 = response_10001.json()
    print("[DEBUG] res_10001:", res_10001)

    # The 10001 price must be different and higher than 3.29 due to the 1.23x multiplier
    assert res_10001["estimated_total"] != 3.29
    assert res_10001["estimated_total"] > 3.29


@pytest.fixture
def setup_organic_milk():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM stores WHERE store_name = 'Walmart'")
    walmart_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM stores WHERE store_name = 'Target'")
    target_id = cur.fetchone()[0]
    
    cur.execute("SELECT id FROM products WHERE canonical_name = 'milk'")
    milk_id = cur.fetchone()[0]
    
    cur.execute(
        "INSERT INTO product_variants (product_id, raw_name, unit, confidence_score) VALUES (?, 'Good & Gather Organic Whole Milk 1 Gal', 'gallon', 1.0)",
        (milk_id,)
    )
    target_variant_id = cur.lastrowid
    
    cur.execute(
        "INSERT INTO product_variants (product_id, raw_name, unit, confidence_score) VALUES (?, 'Great Value Organic Whole Milk 1 Gal', 'gallon', 1.0)",
        (milk_id,)
    )
    walmart_variant_id = cur.lastrowid
    
    cur.execute(
        "INSERT INTO prices (store_id, product_variant_id, price, zip_code, date_collected) VALUES (?, ?, 5.49, '90210', '2026-01-02 02:49:08')",
        (target_id, target_variant_id)
    )
    t_price_id = cur.lastrowid
    
    cur.execute(
        "INSERT INTO prices (store_id, product_variant_id, price, zip_code, date_collected) VALUES (?, ?, 5.29, '90210', '2026-01-02 02:49:08')",
        (walmart_id, walmart_variant_id)
    )
    w_price_id = cur.lastrowid
    
    conn.commit()
    conn.close()
    
    yield walmart_variant_id
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM prices WHERE id IN (?, ?)", (t_price_id, w_price_id))
    cur.execute("DELETE FROM product_variants WHERE id IN (?, ?)", (target_variant_id, walmart_variant_id))
    conn.commit()
    conn.close()


def test_brand_locking_fuzzy_selection(auth_headers, setup_organic_milk):
    walmart_variant_id = setup_organic_milk
    
    response = client.post(
        "/cheapest",
        json={
            "items": [
                {"name": "Good & Gather Organic Whole Milk 1 Gal", "variant_id": walmart_variant_id}
            ],
            "shopper_persona": "fantastically_frugal_francine"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    
    item_res = payload["items"][0]
    # Should pick organic price ($5.29) instead of cheaper generic regular price ($3.29)
    assert item_res["price"] == 5.29
    assert "Organic" in item_res["raw_name"]
