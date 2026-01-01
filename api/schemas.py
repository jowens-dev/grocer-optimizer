from pydantic import BaseModel
from typing import List, Literal

class ItemRequest(BaseModel):
    items: List[str]
    mode: Literal["single_store", "minimize_visits", "maximize_savings"] = "maximize_savings"

