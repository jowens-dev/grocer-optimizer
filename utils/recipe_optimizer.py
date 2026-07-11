from collections import Counter
from typing import Any, Dict, List, Optional

from utils.db_helpers import get_conn
from utils.normalize import canonicalize


def _normalize_store_names(stores: Optional[List[str]]) -> List[str]:
    if not stores:
        return []
    return [store.strip() for store in stores if store and store.strip()]


def _preferred_store_set(preferred_stores: List[str]) -> set[str]:
    return {store.lower() for store in preferred_stores}


def _select_best_candidate(rows: List[Dict[str, Any]], preferred_stores: List[str]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None

    preferred_set = _preferred_store_set(preferred_stores)
    preferred_rows = [row for row in rows if row["store_name"].lower() in preferred_set]
    if preferred_rows:
        return min(preferred_rows, key=lambda row: (row["price"], row["date_collected"]))

    return min(rows, key=lambda row: (row["price"], row["date_collected"]))


def _build_item_store_map(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    store_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        store_map[row["store_name"]] = {
            "price": row["price"],
            "raw_name": row["raw_name"],
            "date_collected": row["date_collected"],
            "unit_price": row.get("unit_price"),
        }
    return store_map


def estimate_recipe_cost(
    recipe_name: str,
    ingredients: List[Dict[str, Any]],
    preferred_stores: Optional[List[str]] = None,
    mode: str = "maximize_savings",
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    normalized_stores = _normalize_store_names(preferred_stores)

    ingredient_results: List[Dict[str, Any]] = []
    store_totals: Dict[str, float] = {}
    stores_used: set[str] = set()
    total_cost = 0.0
    missing_ingredients: List[Dict[str, Any]] = []

    for ingredient in ingredients:
        raw_name = ingredient.get("name", "")
        quantity = ingredient.get("quantity", 1.0)
        unit = ingredient.get("unit")

        canonical_name, confidence_score = canonicalize(raw_name)

        cur.execute(
            """
            SELECT s.store_name, p.price, pv.raw_name, p.date_collected, p.unit_price
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            JOIN product_variants pv ON p.product_variant_id = pv.id
            JOIN products prod ON pv.product_id = prod.id
            WHERE prod.canonical_name = ?
            ORDER BY p.price ASC
            """,
            (canonical_name,),
        )
        rows = [dict(row) for row in cur.fetchall()]

        if not rows:
            missing_ingredients.append({
                "name": raw_name,
                "canonical": canonical_name,
                "reason": "not found in local price database",
            })
            ingredient_results.append({
                "name": raw_name,
                "canonical": canonical_name,
                "quantity": quantity,
                "unit": unit,
                "confidence_score": confidence_score,
                "store": None,
                "price": None,
                "note": "Not available in any store",
            })
            continue

        selected_row = _select_best_candidate(rows, normalized_stores)
        if not selected_row:
            selected_row = rows[0]

        store_name = selected_row["store_name"]
        price = float(selected_row["price"])
        scaled_price = round(price * max(quantity, 1.0), 2) if quantity else round(price, 2)
        total_cost += scaled_price
        stores_used.add(store_name)
        store_totals[store_name] = store_totals.get(store_name, 0.0) + scaled_price

        ingredient_results.append({
            "name": raw_name,
            "canonical": canonical_name,
            "quantity": quantity,
            "unit": unit,
            "confidence_score": confidence_score,
            "store": store_name,
            "price": scaled_price,
            "raw_name": selected_row["raw_name"],
            "date_collected": selected_row["date_collected"],
            "unit_price": selected_row.get("unit_price"),
        })

    if mode == "single_store":
        store_scores = {}
        for store_name in stores_used:
            total = 0.0
            for item in ingredient_results:
                if item["store"] == store_name:
                    total += item["price"] or 0.0
                elif item["price"] is None:
                    total += 1000.0
            store_scores[store_name] = total
        selected_store = min(store_scores.items(), key=lambda item: item[1])[0] if store_scores else None
    elif mode == "minimize_visits":
        store_lookup = {
            item["name"]: _build_item_store_map([
                row for row in rows if False
            ]) for item in []
        }
        del store_lookup
        selected_store = None
        if len(stores_used) == 1:
            selected_store = next(iter(stores_used))
        else:
            selected_store = sorted(stores_used, key=lambda name: (store_totals[name], name))[0]
    else:
        counts = Counter(item["store"] for item in ingredient_results if item.get("store"))
        selected_store = counts.most_common(1)[0][0] if counts else None

    return {
        "recipe_name": recipe_name,
        "mode": mode,
        "preferred_stores": normalized_stores,
        "ingredients": ingredient_results,
        "selected_store": selected_store,
        "estimated_total": round(total_cost, 2),
        "stores_used": sorted(stores_used),
        "store_totals": {name: round(total, 2) for name, total in sorted(store_totals.items())},
        "missing_ingredients": missing_ingredients,
        "source": "local-price-database",
    }
