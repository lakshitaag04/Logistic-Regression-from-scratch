from typing import List, Optional, Union
from pydantic import BaseModel, Field


class Recipe(BaseModel):
    id: Optional[Union[int, str]] = Field(default=None)
    title: str
    ingredients: List[str]
    instructions: Optional[str] = None
    image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    cuisine: Optional[str] = None
    url: Optional[str] = None


class SuggestRequest(BaseModel):
    ingredients: List[str] = Field(default_factory=list)
    top_k: int = 20
    max_missing: Optional[int] = None


class RecipeSuggestion(BaseModel):
    id: Optional[Union[int, str]] = None
    title: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    matched_ingredients: List[str]
    missing_ingredients: List[str]
    score: float
    instructions: Optional[str] = None
    tags: Optional[List[str]] = None
    cuisine: Optional[str] = None


class SuggestResponse(BaseModel):
    suggestions: List[RecipeSuggestion]
    total_considered: int


class DatasetInfo(BaseModel):
    num_recipes: int
    unique_ingredients: int
    dataset_path: str