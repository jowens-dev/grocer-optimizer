from typing import Any, List, Literal, Optional, Union
from pydantic import BaseModel, model_validator, Field


class ShoppingItem(BaseModel):
    name: str
    variant_id: Optional[int] = None


class ItemRequest(BaseModel):
    items: List[ShoppingItem]
    mode: Literal["single_store", "minimize_visits", "maximize_savings"] = "maximize_savings"
    preferred_stores: Optional[List[str]] = None
    
    # AisleOne additions
    tier: Literal["free", "premium"] = "free"
    shopper_persona: Literal["single_store_sam", "balanced_budget_bob", "fantastically_frugal_francine"] = "single_store_sam"
    club_memberships: Optional[List[str]] = None
    zip_code: str = "90210"

    @model_validator(mode="before")
    @classmethod
    def convert_string_items(cls, data: Any) -> Any:
        if isinstance(data, dict) and "items" in data:
            new_items = []
            for item in data["items"]:
                if isinstance(item, str):
                    new_items.append({"name": item, "variant_id": None})
                elif isinstance(item, dict) and "name" not in item:
                    # Fallback or invalid format
                    new_items.append(item)
                else:
                    new_items.append(item)
            data["items"] = new_items
        return data

    def enforce_tiers_and_map_personas(self) -> 'ItemRequest':
        if self.tier == "free":
            # Free tier forces "Single Store Sam" and zero club memberships
            self.shopper_persona = "single_store_sam"
            self.club_memberships = None
        
        # Map shopper_persona to internal execution mode
        if self.shopper_persona == "single_store_sam":
            self.mode = "single_store"
        elif self.shopper_persona == "balanced_budget_bob":
            self.mode = "minimize_visits"
        elif self.shopper_persona == "fantastically_frugal_francine":
            self.mode = "maximize_savings"
            
        return self


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
    
    # AisleOne additions
    tier: Literal["free", "premium"] = "free"
    shopper_persona: Literal["single_store_sam", "balanced_budget_bob", "fantastically_frugal_francine"] = "single_store_sam"
    club_memberships: Optional[List[str]] = None
    zip_code: str = "90210"

    def enforce_tiers_and_map_personas(self) -> 'RecipeEstimateRequest':
        if self.tier == "free":
            self.shopper_persona = "single_store_sam"
            self.club_memberships = None
        
        if self.shopper_persona == "single_store_sam":
            self.mode = "single_store"
        elif self.shopper_persona == "balanced_budget_bob":
            self.mode = "minimize_visits"
        elif self.shopper_persona == "fantastically_frugal_francine":
            self.mode = "maximize_savings"
            
        return self


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

