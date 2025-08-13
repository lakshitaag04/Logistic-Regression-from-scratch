from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import Recipe, RecipeSuggestion


_PUNCT_RE = re.compile(r"[^a-z0-9\s]")

# Simple synonym map. Keys and values should be normalized already (lowercase, no punctuation)
RAW_SYNONYMS: Dict[str, str] = {
    "bell pepper": "capsicum",
    "bell peppers": "capsicum",
    "scallion": "green onion",
    "scallions": "green onion",
    "spring onion": "green onion",
    "spring onions": "green onion",
    "garbanzo bean": "chickpea",
    "garbanzo beans": "chickpea",
    "chickpeas": "chickpea",
    "cilantro": "coriander",
    "confectioners sugar": "powdered sugar",
    "icing sugar": "powdered sugar",
    "bicarbonate of soda": "baking soda",
    "aubergine": "eggplant",
    "curd": "yogurt",
}

# Pantry items we ignore in scoring when computing coverage
PANTRY_INGREDIENTS: Set[str] = {
    "salt",
    "black pepper",
    "pepper",
    "water",
    "oil",
    "olive oil",
    "vegetable oil",
    "butter",
    "sugar",
}


def _normalize_text(text: str) -> str:
    cleaned = _PUNCT_RE.sub(" ", text.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _singularize_basic(word: str) -> str:
    # naive singularization; avoids external deps
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def normalize_ingredient(ingredient: str) -> str:
    text = _normalize_text(ingredient)
    # collapse multi-word synonyms first
    # We apply mapping on full phrase when possible
    if text in RAW_SYNONYMS:
        text = RAW_SYNONYMS[text]
    # singularize each token and rebuild phrase
    tokens = [_singularize_basic(t) for t in text.split()]
    normalized = " ".join(tokens).strip()
    if normalized in RAW_SYNONYMS:
        normalized = RAW_SYNONYMS[normalized]
    return normalized


def normalize_ingredient_set(ingredients: Iterable[str]) -> Set[str]:
    return {normalize_ingredient(i) for i in ingredients if i and i.strip()}


@dataclass
class IndexedRecipe:
    original: Recipe
    normalized_ingredients: Set[str]


class RecipeIndex:
    def __init__(self, recipes: List[Recipe]):
        self.indexed: List[IndexedRecipe] = []
        self.ingredient_frequency: Dict[str, int] = {}

        for recipe in recipes:
            normalized = normalize_ingredient_set(recipe.ingredients)
            # filter pantry items out for scoring set but keep original
            normalized_no_pantry = {i for i in normalized if i not in PANTRY_INGREDIENTS}
            indexed = IndexedRecipe(original=recipe, normalized_ingredients=normalized_no_pantry)
            self.indexed.append(indexed)
            for ing in normalized:
                self.ingredient_frequency[ing] = self.ingredient_frequency.get(ing, 0) + 1

    def suggest(
        self,
        user_ingredients: Iterable[str],
        top_k: int = 20,
        max_missing: Optional[int] = None,
    ) -> Tuple[List[RecipeSuggestion], int]:
        user_norm_set = normalize_ingredient_set(user_ingredients)

        # For partial matching, create expanded match map where a user term matches recipe term if substring either way
        def compute_match_set(recipe_terms: Set[str]) -> Tuple[Set[str], Set[str]]:
            matched: Set[str] = set()
            for r in recipe_terms:
                for u in user_norm_set:
                    if u == r or u in r or r in u:
                        matched.add(r)
                        break
            missing = recipe_terms - matched
            return matched, missing

        scored: List[Tuple[float, int, IndexedRecipe, Set[str], Set[str]]] = []
        for rec in self.indexed:
            recipe_terms = rec.normalized_ingredients
            matched, missing = compute_match_set(recipe_terms)
            matched_count = len(matched)
            if max_missing is not None and len(missing) > max_missing:
                continue

            precision = matched_count / max(len(user_norm_set), 1)
            recall = matched_count / max(len(recipe_terms), 1)
            score = 0.7 * recall + 0.3 * precision - 0.02 * len(missing)

            # small title boost if any user term appears in title
            title_norm = _normalize_text(rec.original.title)
            if any(u in title_norm for u in user_norm_set):
                score += 0.05

            scored.append((score, matched_count, rec, matched, missing))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top = scored[:top_k]

        suggestions: List[RecipeSuggestion] = []
        for score, _matched_count, rec, matched, missing in top:
            suggestions.append(
                RecipeSuggestion(
                    id=rec.original.id,
                    title=rec.original.title,
                    image_url=rec.original.image_url,
                    url=rec.original.url,
                    matched_ingredients=sorted(matched),
                    missing_ingredients=sorted(missing),
                    score=round(float(score), 4),
                    instructions=rec.original.instructions,
                    tags=rec.original.tags,
                    cuisine=rec.original.cuisine,
                )
            )
        return suggestions, len(self.indexed)

    def ingredients(self, query: Optional[str] = None, limit: int = 50) -> List[Tuple[str, int]]:
        items = list(self.ingredient_frequency.items())
        if query:
            q = _normalize_text(query)
            items = [(k, v) for k, v in items if q in k]
        items.sort(key=lambda kv: (-kv[1], kv[0]))
        return items[:limit]


def load_recipes_from_file(path: str) -> List[Recipe]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset file not found at {path}")

    _, ext = os.path.splitext(path)
    ext = ext.lower()

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Expecting list of recipe objects
        recipes: List[Recipe] = []
        for idx, item in enumerate(data):
            title = item.get("title") or item.get("name")
            if not title:
                continue
            ingredients_raw = item.get("ingredients")
            if isinstance(ingredients_raw, str):
                ingredients_list = [s.strip() for s in ingredients_raw.split(",") if s.strip()]
            elif isinstance(ingredients_raw, list):
                ingredients_list = [str(x) for x in ingredients_raw if str(x).strip()]
            else:
                ingredients_list = []

            recipe = Recipe(
                id=item.get("id", idx),
                title=title,
                ingredients=ingredients_list,
                instructions=item.get("instructions") or item.get("directions") or None,
                image_url=item.get("image") or item.get("image_url"),
                tags=item.get("tags"),
                cuisine=item.get("cuisine"),
                url=item.get("url"),
            )
            recipes.append(recipe)
        return recipes

    elif ext == ".csv":
        # minimal csv parser without pandas
        import csv

        recipes: List[Recipe] = []
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for idx, row in enumerate(reader):
                title = row.get("title") or row.get("name")
                if not title:
                    continue
                ingredients_raw = row.get("ingredients") or ""
                ingredients_list = [s.strip() for s in ingredients_raw.split(",") if s.strip()]
                recipe = Recipe(
                    id=row.get("id") or idx,
                    title=title,
                    ingredients=ingredients_list,
                    instructions=row.get("instructions") or row.get("directions"),
                    image_url=row.get("image") or row.get("image_url"),
                    tags=[t.strip() for t in (row.get("tags") or "").split(",") if t.strip()] or None,
                    cuisine=row.get("cuisine") or None,
                    url=row.get("url") or None,
                )
                recipes.append(recipe)
        return recipes

    else:
        raise ValueError(f"Unsupported dataset extension: {ext}")