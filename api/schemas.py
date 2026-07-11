from typing import Any, List, Literal, Optional

from pydantic import BaseModel


class ItemRequest(BaseModel):
    items: List[str]
    mode: Literal["single_store", "minimize_visits", "maximize_savings"] = "maximize_savings"
    preferred_stores: Optional[List[str]] = None


class RecipeIngredient(BaseModel):
    name: str
    quantity: float = 1.0
    unit: Optional[str] = None


class RecipeInput(BaseModel):
    name: str
    ingredients: List[RecipeIngredient]


class RecipeEstimateRequest(RecipeInput):
    mode: Literal["single_store", "minimize_visits", "maximize_savings"] = "maximize_savings"
    preferred_stores: Optional[List[str]] = None


class RecipeEstimateResponse(BaseModel):
    recipe_name: str
    mode: str
    preferred_stores: List[str]
    ingredients: List[dict[str, Any]]
    selected_store: Optional[str]
    estimated_total: float
    stores_used: List[str]
    store_totals: dict[str, float]
    missing_ingredients: List[dict[str, Any]]
    source: str

