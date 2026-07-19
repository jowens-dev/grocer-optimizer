
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.schemas import ItemRequest, RecipeEstimateRequest, RecipeEstimateResponse, RecipeInput
from utils.db_helpers import get_conn
from utils.normalize import canonicalize
from utils.recipe_optimizer import estimate_recipe_cost
from api.auth import hash_password, verify_password, create_token, get_current_user

app = FastAPI(title="Grocery Price Optimizer")

# Configure CORS restrictions based on environment
origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sliding Window Rate Limiting (In-Memory per client IP)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 9999 if os.environ.get("AISLEONE_ENV") == "test" else 15
auth_attempts = defaultdict(list)

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    # Filter out expired timestamps
    auth_attempts[ip] = [t for t in auth_attempts[ip] if now - t < RATE_LIMIT_WINDOW]
    max_reqs = 9999 if os.environ.get("AISLEONE_ENV") == "test" else 15
    if len(auth_attempts[ip]) >= max_reqs:
        return False
    auth_attempts[ip].append(now)
    return True

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    tier: Literal["free", "premium"]
    club_memberships: List[str]
    zip_code: str

@app.post("/auth/register")
def register(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please try again later.")
        
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM users WHERE username = ?", (req.username,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
        
    pw_hash = hash_password(req.password)
    cur.execute("""
        INSERT INTO users (username, password_hash, tier, club_memberships, zip_code, created_at, updated_at)
        VALUES (?, ?, 'free', '[]', '90210', datetime('now'), datetime('now'))
    """, (req.username, pw_hash))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "User registered successfully"}

@app.post("/auth/token")
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
        
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, tier, club_memberships, zip_code FROM users WHERE username = ?", (req.username,))
    row = cur.fetchone()
    conn.close()
    
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = create_token({
        "username": req.username,
        "tier": row["tier"]
    })
    
    try:
        clubs = json.loads(row["club_memberships"])
    except Exception:
        clubs = []
        
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": req.username,
            "tier": row["tier"],
            "club_memberships": clubs,
            "zip_code": row["zip_code"]
        }
    }

@app.post("/users/profile")
def update_profile(req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET tier = ?, club_memberships = ?, zip_code = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (req.tier, json.dumps(req.club_memberships), req.zip_code, current_user["id"]))
    conn.commit()
    
    # Check if local prices exist for this zip code
    cur.execute("SELECT COUNT(*) FROM prices WHERE zip_code = ?", (req.zip_code,))
    count = cur.fetchone()[0]
    if count == 0:
        # Clone default market pricing catalog to this new location
        cur.execute("""
            INSERT INTO prices (store_id, product_variant_id, price, unit_price, zip_code, date_collected)
            SELECT store_id, product_variant_id, price, unit_price, ?, date_collected
            FROM prices WHERE zip_code = '90210'
        """, (req.zip_code,))
        conn.commit()
        
    conn.close()
    return {"status": "success", "tier": req.tier, "club_memberships": req.club_memberships, "zip_code": req.zip_code}

@app.get("/users/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "tier": current_user["tier"],
        "club_memberships": current_user["club_memberships"],
        "zip_code": current_user["zip_code"]
    }

RECIPE_STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "recipes.json"


def _load_recipes() -> List[dict[str, Any]]:
    if not RECIPE_STORE_PATH.exists():
        return []
    try:
        return json.loads(RECIPE_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save_recipes(recipes: List[dict[str, Any]]) -> None:
    RECIPE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECIPE_STORE_PATH.write_text(json.dumps(recipes, indent=2), encoding="utf-8")


@app.get("/health")
def health_check():
    return {"status": "ok", "recipes_file": str(RECIPE_STORE_PATH)}


@app.post("/recipes", response_model=RecipeInput)
def create_recipe(req: RecipeInput):
    """Persist a recipe locally so it can be reused later."""
    recipes = _load_recipes()
    recipes.append(req.model_dump())
    _save_recipes(recipes)
    return req


@app.get("/recipes", response_model=List[RecipeInput])
def list_recipes():
    """List saved recipes."""
    return _load_recipes()


@app.post("/recipes/estimate", response_model=RecipeEstimateResponse)
def estimate_recipe(req: RecipeEstimateRequest, current_user: dict = Depends(get_current_user)):
    """Estimate the cheapest way to buy the ingredients for a recipe."""
    req.tier = current_user["tier"]
    req.club_memberships = current_user["club_memberships"]
    req.zip_code = current_user["zip_code"]
    req.enforce_tiers_and_map_personas()
    
    return estimate_recipe_cost(
        recipe_name=req.name,
        ingredients=[ingredient.model_dump() for ingredient in req.ingredients],
        preferred_stores=req.preferred_stores,
        mode=req.mode,
        club_memberships=req.club_memberships,
        zip_code=req.zip_code,
    )


@app.post("/cheapest")
def cheapest_list(req: ItemRequest, current_user: dict = Depends(get_current_user)):
    """Find the cheapest way to buy a list of items"""
    req.tier = current_user["tier"]
    req.club_memberships = current_user["club_memberships"]
    req.zip_code = current_user["zip_code"]
    req.enforce_tiers_and_map_personas()
    
    conn = get_conn()
    cur = conn.cursor()
    
    if req.mode == "single_store":
        return _single_store_optimization(cur, req)
    elif req.mode == "minimize_visits":
        return _minimize_visits_optimization(cur, req)
    else:  # maximize_savings
        return _maximize_savings_optimization(cur, req)

def _get_item_prices(cur, raw_item: str, variant_id: Optional[int], zip_code: str, preferred_stores: Optional[List[str]], club_memberships: Optional[List[str]]) -> List[dict]:
    canonical, confidence_score = canonicalize(raw_item)
    
    selected_variant_name = None
    canonical_product_id = None
    if variant_id is not None:
        cur.execute("SELECT raw_name, product_id FROM product_variants WHERE id = ?", (variant_id,))
        v_row = cur.fetchone()
        if v_row:
            selected_variant_name = v_row["raw_name"]
            canonical_product_id = v_row["product_id"]
            
    if canonical_product_id is not None:
        # User selected a specific variant, query all variants for that product family
        query = """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected, s.is_club, pv.id AS variant_id, p.unit_price
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            WHERE pv.product_id = ? AND p.zip_code = ?
        """
        params = [canonical_product_id, zip_code]
    else:
        # Generic product query
        query = """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected, s.is_club, pv.id AS variant_id, p.unit_price
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            JOIN products prod ON pv.product_id = prod.id
            WHERE prod.canonical_name = ? AND p.zip_code = ?
        """
        params = [canonical, zip_code]
        
    if preferred_stores:
        placeholders = ",".join("?" * len(preferred_stores))
        query += f" AND s.store_name IN ({placeholders})"
        params.extend(preferred_stores)
        
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    
    # Filter club stores based on user profile tier/memberships
    allowed_clubs = {c.lower() for c in club_memberships} if club_memberships else set()
    rows = [row for row in rows if not row["is_club"] or row["store_name"].lower() in allowed_clubs]
    
    if not rows:
        return []
        
    # Group rows by store name to find the best candidate variant per store
    store_options = {}
    for row in rows:
        store = row["store_name"]
        if store not in store_options:
            store_options[store] = []
        store_options[store].append(row)
        
    final_rows = []
    for store, options in store_options.items():
        if selected_variant_name is not None:
            # Fuzzy match variant names to find the closest brand match
            from rapidfuzz import fuzz
            best_row = max(options, key=lambda r: fuzz.ratio(selected_variant_name.lower(), r["raw_name"].lower()))
            score = fuzz.ratio(selected_variant_name.lower(), best_row["raw_name"].lower())
            # If the closest match is less than 75% similar, exclude this store as it does not sell a comparable brand
            if score >= 75:
                final_rows.append(best_row)
        else:
            # Pick cheapest variant for standard optimization
            best_row = min(options, key=lambda r: r["price"])
            final_rows.append(best_row)
        
    # Sort by price ascending
    final_rows.sort(key=lambda r: r["price"])
    return final_rows


def _single_store_optimization(cur, req: ItemRequest):
    """Find the best single store for all items"""
    store_scores = {}
    item_availability = {}
    
    for item in req.items:
        raw_item = item.name
        variant_id = item.variant_id
        canonical, confidence_score = canonicalize(raw_item)
        
        rows = _get_item_prices(cur, raw_item, variant_id, req.zip_code, req.preferred_stores, req.club_memberships)
        
        item_availability[canonical] = {}
        for row in rows:
            store_name = row["store_name"]
            item_availability[canonical][store_name] = {
                "price": row["price"],
                "raw_name": row["raw_name"],
                "date_collected": row["date_collected"],
                "confidence_score": confidence_score
            }
    
    # Calculate store scores (lower is better)
    for store_name in set().union(*[stores.keys() for stores in item_availability.values()]):
        total_cost = 0
        items_available = 0
        
        for canonical, stores in item_availability.items():
            if store_name in stores:
                total_cost += stores[store_name]["price"]
                items_available += 1
        
        # Penalize stores that don't have all items
        availability_penalty = (len(req.items) - items_available) * 1000
        store_scores[store_name] = total_cost + availability_penalty
    
    if not store_scores:
        return {"error": "No stores found matching criteria"}
    
    # Select best store
    best_store = min(store_scores.keys(), key=lambda x: store_scores[x])
    
    # Build results for best store
    results = []
    total_cost = 0
    
    for item in req.items:
        raw_item = item.name
        variant_id = item.variant_id
        canonical, confidence_score = canonicalize(raw_item)
        if canonical in item_availability and best_store in item_availability[canonical]:
            item_data = item_availability[canonical][best_store]
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": confidence_score,
                "store": best_store,
                "price": item_data["price"],
                "raw_name": item_data["raw_name"],
                "date_collected": item_data["date_collected"]
            })
            total_cost += item_data["price"]
        else:
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": confidence_score,
                "store": None,
                "price": None,
                "note": "Not available at selected store"
            })
    
    return {
        "mode": "single_store",
        "selected_store": best_store,
        "items": results,
        "total_cost": total_cost,
        "stores_used": [best_store]
    }


def _minimize_visits_optimization(cur, req: ItemRequest):
    """Minimize number of stores while keeping costs reasonable"""
    item_store_prices = {}
    
    for item in req.items:
        raw_item = item.name
        variant_id = item.variant_id
        canonical, confidence_score = canonicalize(raw_item)
        
        rows = _get_item_prices(cur, raw_item, variant_id, req.zip_code, req.preferred_stores, req.club_memberships)
        
        item_store_prices[canonical] = {
            "raw_item": raw_item,
            "confidence_score": confidence_score,
            "stores": {}
        }
        
        for row in rows:
            item_store_prices[canonical]["stores"][row["store_name"]] = {
                "price": row["price"],
                "raw_name": row["raw_name"],
                "date_collected": row["date_collected"]
            }
    
    # Greedy algorithm: pick stores that cover most items at reasonable prices
    selected_items = {}
    stores_used = set()
    
    while len(selected_items) < len(req.items):
        best_store = None
        best_score = float('-inf')
        
        # Calculate score for each store (items covered / cost ratio)
        for store_name in set().union(*[item_data["stores"].keys() for item_data in item_store_prices.values()]):
            if store_name in stores_used:
                continue
                
            items_covered = 0
            total_cost = 0
            
            for canonical, item_data in item_store_prices.items():
                if canonical not in selected_items and store_name in item_data["stores"]:
                    items_covered += 1
                    total_cost += item_data["stores"][store_name]["price"]
            
            if items_covered > 0:
                score = items_covered / (total_cost + 1)
                if score > best_score:
                    best_score = score
                    best_store = store_name
        
        if best_store:
            stores_used.add(best_store)
            for canonical, item_data in item_store_prices.items():
                if canonical not in selected_items and best_store in item_data["stores"]:
                    selected_items[canonical] = {
                        "store": best_store,
                        "data": item_data["stores"][best_store],
                        "raw_item": item_data["raw_item"],
                        "confidence_score": item_data["confidence_score"]
                    }
        else:
            break
    
    # Build results
    results = []
    store_totals = {}
    total_cost = 0
    
    for item in req.items:
        raw_item = item.name
        canonical, confidence_score = canonicalize(raw_item)
        if canonical in selected_items:
            sel_item = selected_items[canonical]
            store = sel_item["store"]
            price = sel_item["data"]["price"]
            
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": sel_item["confidence_score"],
                "store": store,
                "price": price,
                "raw_name": sel_item["data"]["raw_name"],
                "date_collected": sel_item["data"]["date_collected"]
            })
            
            store_totals[store] = store_totals.get(store, 0) + price
            total_cost += price
        else:
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": confidence_score,
                "store": None,
                "price": None,
                "note": "Not available in selected stores"
            })
    
    return {
        "mode": "minimize_visits",
        "items": results,
        "stores_used": list(stores_used),
        "store_totals": store_totals,
        "total_cost": total_cost,
        "num_stores": len(stores_used)
    }


def _maximize_savings_optimization(cur, req: ItemRequest):
    """Find absolute cheapest for each item regardless of store"""
    results = []
    store_totals = {}
    stores_used = set()
    total_cost = 0

    for item in req.items:
        raw_item = item.name
        variant_id = item.variant_id
        canonical, confidence_score = canonicalize(raw_item)

        rows = _get_item_prices(cur, raw_item, variant_id, req.zip_code, req.preferred_stores, req.club_memberships)

        if rows:
            row = rows[0]
            result_store_name = row["store_name"]
            result_price = row["price"]
            result_raw_name = row["raw_name"]
            result_date_collected = row["date_collected"]
            result_unit_price = row.get("unit_price")

            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": confidence_score,
                "store": result_store_name,
                "price": result_price,
                "unit_price": result_unit_price,
                "raw_name": result_raw_name,
                "date_collected": result_date_collected
            })

            stores_used.add(result_store_name)
            store_totals[result_store_name] = store_totals.get(result_store_name, 0.0) + result_price
            total_cost += result_price
        else:
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": confidence_score,
                "store": None,
                "price": None,
                "note": "Not available in selected stores"
            })

    return {
        "mode": "maximize_savings",
        "items": results,
        "stores_used": list(stores_used),
        "store_totals": store_totals,
        "total_cost": total_cost,
        "num_stores": len(stores_used)
    }

@app.get("/search")
def search_products(q: str, current_user: dict = Depends(get_current_user)):
    """Search products and variants in the local database comparing store prices."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.canonical_name, s.store_name, pr.price, pv.raw_name, pr.unit_price, s.is_club, pv.id AS variant_id
        FROM products p
        JOIN product_variants pv ON pv.product_id = p.id
        JOIN prices pr ON pr.product_variant_id = pv.id
        JOIN stores s ON pr.store_id = s.id
        WHERE (p.canonical_name LIKE ? OR pv.raw_name LIKE ?) AND pr.zip_code = ?
        ORDER BY p.canonical_name, pr.price ASC
        """,
        (f"%{q}%", f"%{q}%", current_user["zip_code"])
    )
    return [dict(row) for row in cur.fetchall()]

# Mount static files dashboard
static_dir = Path(__file__).resolve().parents[1] / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

