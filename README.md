# PantryChef

A simple web app where users enter ingredients they have, and it suggests matching recipes from a curated dataset.

## Quickstart

1. Create and activate a virtual environment (optional but recommended)

```bash
python3 -m venv .venv && source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Place your dataset at `/workspace/data/recipes.json` (default), or set the `DATA_PATH` environment variable to point to your dataset file. Supported formats: JSON (list of objects) or CSV.

- Expected fields per recipe (flexible):
  - `title` (or `name`)
  - `ingredients` (array of strings or comma-separated string)
  - Optional: `instructions`, `image_url` (or `image`), `tags` (array or comma-separated), `cuisine`, `id`, `url`

4. Run the server

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000`.

## API

- `GET /health` — health check
- `GET /api/dataset/info` — dataset stats
- `GET /api/ingredients?query=tom&limit=8` — ingredient suggestions
- `POST /api/suggest` — body:

```json
{
  "ingredients": ["tomato", "onion"],
  "top_k": 20,
  "max_missing": 3
}
```

## Using your own dataset

- Put your file at `/workspace/data/recipes.json` or export `DATA_PATH=/absolute/path/to/your/file.json` before starting the server.
- JSON should be a list of objects. If `ingredients` is a string, items are split by commas.

## Notes

- Ingredient matching uses simple normalization (case folding, punctuation removal, light singularization) and basic synonyms (e.g., "scallion" → "green onion").
- Pantry items (salt, oil, water, etc.) are ignored when computing coverage.
