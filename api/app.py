
# app.py (Enhanced FastAPI)
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.schemas import ItemRequest, RecipeEstimateRequest, RecipeEstimateResponse, RecipeInput
from utils.db_helpers import get_conn
from utils.normalize import canonicalize
from utils.recipe_optimizer import estimate_recipe_cost

app = FastAPI(title="Grocery Price Optimizer")

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
def estimate_recipe(req: RecipeEstimateRequest):
    """Estimate the cheapest way to buy the ingredients for a recipe."""
    return estimate_recipe_cost(
        recipe_name=req.name,
        ingredients=[ingredient.model_dump() for ingredient in req.ingredients],
        preferred_stores=req.preferred_stores,
        mode=req.mode,
    )


@app.post("/cheapest")
def cheapest_list(req: ItemRequest):
    """Find the cheapest way to buy a list of items"""
    conn = get_conn()
    cur = conn.cursor()
    
    if req.mode == "single_store":
        return _single_store_optimization(cur, req)
    elif req.mode == "minimize_visits":
        return _minimize_visits_optimization(cur, req)
    else:  # maximize_savings
        return _maximize_savings_optimization(cur, req)

def _single_store_optimization(cur, req: ItemRequest):
    """Find the best single store for all items"""
    store_scores = {}
    item_availability = {}
    
    for raw_item in req.items:
        canonical, confidence_score = canonicalize(raw_item)
        
        # Get all available prices for this item
        query = """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            JOIN products prod ON pv.product_id = prod.id
            WHERE prod.canonical_name = ?
        """
        params = [canonical]
        
        # Apply preferred stores filter
        if req.preferred_stores:
            placeholders = ",".join("?" * len(req.preferred_stores))
            query += f" AND s.store_name IN ({placeholders})"
            params.extend(req.preferred_stores)
            
        query += " ORDER BY p.price ASC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        item_availability[canonical] = {}
        for row in rows:
            store_name = row["store_name"]
            if store_name not in item_availability[canonical]:
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
    
    for raw_item in req.items:
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
    
    for raw_item in req.items:
        canonical, confidence_score = canonicalize(raw_item)
        
        query = """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            JOIN products prod ON pv.product_id = prod.id
            WHERE prod.canonical_name = ?
        """
        params = [canonical]
        
        if req.preferred_stores:
            placeholders = ",".join("?" * len(req.preferred_stores))
            query += f" AND s.store_name IN ({placeholders})"
            params.extend(req.preferred_stores)
            
        query += " ORDER BY p.price ASC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
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
        for store_name in set().union(*[item["stores"].keys() for item in item_store_prices.values()]):
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
    
    for raw_item in req.items:
        canonical, confidence_score = canonicalize(raw_item)
        if canonical in selected_items:
            item = selected_items[canonical]
            store = item["store"]
            price = item["data"]["price"]
            
            results.append({
                "query": raw_item,
                "canonical": canonical,
                "confidence_score": item["confidence_score"],
                "store": store,
                "price": price,
                "raw_name": item["data"]["raw_name"],
                "date_collected": item["data"]["date_collected"]
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

    for raw_item in req.items:
        canonical, confidence_score = canonicalize(raw_item)

        query = """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected, p.unit_price
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            JOIN products prod ON pv.product_id = prod.id
            WHERE prod.canonical_name = ?
        """

        params = [canonical]

        if req.preferred_stores:
            placeholders = ",".join("?" * len(req.preferred_stores))
            query += f" AND s.store_name IN ({placeholders})"
            params.extend(req.preferred_stores)

        query += " ORDER BY p.price ASC LIMIT 1"

        cur.execute(query, params)
        row = cur.fetchone()

        if row:
            # Use dictionary-style access with column names
            result_store_name = row["store_name"]
            result_price = row["price"]
            result_raw_name = row["raw_name"]
            result_date_collected = row["date_collected"]
            result_unit_price = row["unit_price"]

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
                "note": "Not available in any store"
            })

    return {
        "mode": "maximize_savings",
        "items": results,
        "stores_used": list(stores_used),
        "store_totals": store_totals,
        "total_cost": total_cost,
        "num_stores": len(stores_used)
    }

