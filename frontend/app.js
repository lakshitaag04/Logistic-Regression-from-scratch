const ingredientInput = document.getElementById('ingredient-text');
const addBtn = document.getElementById('add-btn');
const chipsContainer = document.getElementById('ingredient-input');
const resultsEl = document.getElementById('results');
const findBtn = document.getElementById('find-btn');
const suggestionsEl = document.getElementById('suggestions');
const datasetInfoEl = document.getElementById('dataset-info');
const topKEl = document.getElementById('top-k');
const maxMissingEl = document.getElementById('max-missing');

let ingredients = [];
let suggestionAbortController = null;

function renderChips() {
  // remove existing chips except the input and add button
  [...chipsContainer.querySelectorAll('.chip')].forEach(el => el.remove());
  ingredients.forEach((ing, idx) => {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.innerHTML = `<span>${ing}</span><span class="remove" title="Remove">✕</span>`;
    chip.querySelector('.remove').addEventListener('click', () => {
      ingredients.splice(idx, 1);
      renderChips();
    });
    chipsContainer.insertBefore(chip, ingredientInput);
  });
}

function addIngredientFromInput() {
  const value = ingredientInput.value.trim();
  if (!value) return;
  value.split(',').map(s => s.trim()).filter(Boolean).forEach(v => {
    if (!ingredients.includes(v)) ingredients.push(v);
  });
  ingredientInput.value = '';
  hideSuggestions();
  renderChips();
}

addBtn.addEventListener('click', addIngredientFromInput);
ingredientInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    addIngredientFromInput();
  }
});

async function fetchSuggestions(prefix) {
  if (suggestionAbortController) suggestionAbortController.abort();
  suggestionAbortController = new AbortController();
  const params = new URLSearchParams();
  if (prefix) params.set('query', prefix);
  params.set('limit', '8');
  const res = await fetch(`/api/ingredients?${params}`, { signal: suggestionAbortController.signal });
  if (!res.ok) return [];
  const data = await res.json();
  return data.map(d => d.ingredient);
}

function showSuggestions(items) {
  suggestionsEl.innerHTML = '';
  if (!items.length) {
    hideSuggestions();
    return;
  }
  items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'item';
    div.textContent = item;
    div.addEventListener('click', () => {
      if (!ingredients.includes(item)) ingredients.push(item);
      ingredientInput.value = '';
      hideSuggestions();
      renderChips();
    });
    suggestionsEl.appendChild(div);
  });
  suggestionsEl.hidden = false;
}

function hideSuggestions() {
  suggestionsEl.hidden = true;
  suggestionsEl.innerHTML = '';
}

ingredientInput.addEventListener('input', async () => {
  const q = ingredientInput.value.trim();
  if (!q) { hideSuggestions(); return; }
  const items = await fetchSuggestions(q);
  showSuggestions(items);
});

document.addEventListener('click', (e) => {
  if (!suggestionsEl.contains(e.target) && e.target !== ingredientInput) {
    hideSuggestions();
  }
});

function recipeCardHtml(s) {
  const image = s.image_url || 'https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=600&q=60';
  const matched = s.matched_ingredients.map(i => `<span class="badge">${i}</span>`).join(' ');
  const missing = s.missing_ingredients.map(i => `<span class="badge">${i}</span>`).join(' ');
  const tags = (s.tags || []).slice(0, 5).map(t => `<span class="badge">${t}</span>`).join(' ');
  const cuisine = s.cuisine ? `<span class="badge">${s.cuisine}</span>` : '';
  const more = s.url ? `<a href="${s.url}" target="_blank" rel="noopener">Source</a>` : '';
  const instructions = s.instructions ? `<details><summary>Instructions</summary><p>${s.instructions}</p></details>` : '';
  return `
  <div class="recipe-card">
    <img src="${image}" alt="${s.title}" />
    <div>
      <h3>${s.title}</h3>
      <div class="meta">Score ${s.score.toFixed(2)} • Matches (${s.matched_ingredients.length}) • Missing (${s.missing_ingredients.length})</div>
      <div class="badges" style="margin-top:6px;">${matched}</div>
      ${missing ? `<div class="badges" style="margin-top:6px;">Need: ${missing}</div>` : ''}
      ${tags || cuisine ? `<div class="badges" style="margin-top:6px;">${cuisine} ${tags}</div>` : ''}
      <div style="margin-top:8px;">${more}</div>
      <div style="margin-top:8px;">${instructions}</div>
    </div>
  </div>`;
}

async function findRecipes() {
  resultsEl.innerHTML = '<p class="muted">Searching…</p>';
  const payload = {
    ingredients,
    top_k: Math.max(1, Math.min(50, parseInt(topKEl.value || '20', 10))),
    max_missing: Math.max(0, Math.min(10, parseInt(maxMissingEl.value || '3', 10)))
  };
  const res = await fetch('/api/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    resultsEl.innerHTML = '<p class="muted">Failed to fetch suggestions.</p>';
    return;
  }
  const data = await res.json();
  if (!data.suggestions.length) {
    resultsEl.innerHTML = '<p class="muted">No recipes match your ingredients. Try allowing more missing items or adding more ingredients.</p>';
    return;
  }
  resultsEl.innerHTML = data.suggestions.map(recipeCardHtml).join('');
}

findBtn.addEventListener('click', findRecipes);

async function loadDatasetInfo() {
  try {
    const res = await fetch('/api/dataset/info');
    const info = await res.json();
    datasetInfoEl.textContent = `${info.num_recipes} recipes • ${info.unique_ingredients} ingredients • ${info.dataset_path}`;
  } catch (e) {
    datasetInfoEl.textContent = 'unavailable';
  }
}

loadDatasetInfo();