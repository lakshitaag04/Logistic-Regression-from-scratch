import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import DatasetInfo, SuggestRequest, SuggestResponse
from .recipe_matcher import RecipeIndex, load_recipes_from_file


DATA_PATH_ENV = "DATA_PATH"
DEFAULT_DATASET = "/workspace/data/recipes.json"
FALLBACK_SAMPLE_DATASET = "/workspace/data/sample_recipes.json"
FRONTEND_DIR = "/workspace/frontend"

app = FastAPI(title="PantryChef", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

recipe_index: Optional[RecipeIndex] = None
active_dataset_path: Optional[str] = None


@app.on_event("startup")
async def startup_event() -> None:
    global recipe_index, active_dataset_path
    dataset_path = os.getenv(DATA_PATH_ENV, DEFAULT_DATASET)
    if not os.path.exists(dataset_path):
        # fallback to sample
        dataset_path = FALLBACK_SAMPLE_DATASET
    try:
        recipes = load_recipes_from_file(dataset_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load dataset at {dataset_path}: {exc}")

    recipe_index = RecipeIndex(recipes)
    active_dataset_path = dataset_path


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dataset/info", response_model=DatasetInfo)
async def dataset_info() -> DatasetInfo:
    if recipe_index is None or active_dataset_path is None:
        raise HTTPException(status_code=503, detail="Index not ready")
    return DatasetInfo(
        num_recipes=len(recipe_index.indexed),
        unique_ingredients=len(recipe_index.ingredient_frequency),
        dataset_path=active_dataset_path,
    )


@app.get("/api/ingredients")
async def ingredients(query: Optional[str] = Query(default=None), limit: int = Query(default=50, ge=1, le=200)) -> JSONResponse:
    if recipe_index is None:
        raise HTTPException(status_code=503, detail="Index not ready")
    items = recipe_index.ingredients(query=query, limit=limit)
    return JSONResponse([{"ingredient": k, "count": v} for k, v in items])


@app.post("/api/suggest", response_model=SuggestResponse)
async def suggest(payload: SuggestRequest) -> SuggestResponse:
    if recipe_index is None:
        raise HTTPException(status_code=503, detail="Index not ready")
    suggestions, total = recipe_index.suggest(
        user_ingredients=payload.ingredients,
        top_k=payload.top_k,
        max_missing=payload.max_missing,
    )
    return SuggestResponse(suggestions=suggestions, total_considered=total)

# Serve frontend after API routes are defined
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")