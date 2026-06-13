# smart-suggest

A recommendation system with built-in A/B testing infrastructure, statistical analysis, and KPI tracking — built from scratch in Python.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI (app.py)                     │
└────────────┬──────────────┬───────────────┬────────────────-┘
             │              │               │
    ┌────────▼──────┐  ┌────▼──────┐  ┌────▼──────────┐
    │  recommenders │  │ ab_testing│  │   tracking    │
    │  ├── cf.py    │  │ ├─manager │  │  interaction  │
    │  ├── content  │  │ └─logger  │  │   _tracker    │
    │  └── simil..  │  └───────────┘  └───────────────┘
    └───────┬───────┘
            │
    ┌───────▼───────┐   ┌──────────────┐   ┌───────────────┐
    │  features/    │   │  analysis.py │   │  metrics.py   │
    │  item_feat..  │   │  (KPIs)      │   │  (pure math)  │
    └───────────────┘   └──────┬───────┘   └───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  significance.py    │
                    │  interpretation.py  │
                    └─────────────────────┘
```

---

## Recommendation Strategies

### Strategy A — Collaborative Filtering (v1)

**Idea:** users who agreed in the past will agree in the future.

1. Build a weighted user-item interaction matrix (view=1, click=3, purchase=5)
2. Compute pairwise cosine similarity between users
3. Find the top-K nearest neighbours for the target user
4. Score unseen items by `Σ similarity × neighbour_weight` and return top-N
5. **Cold-start fill:** items with zero interactions from anyone are scored via content similarity to the user's liked items (discounted ×0.05) and appended after the top-N CF results — they can never be crowded out by the count limit

**Strength:** discovers unexpected items through shared taste communities  
**Weakness:** cold start for new users with no interaction history at all

### Strategy B — Content-Based Filtering (v2)

**Idea:** recommend items similar to what this user has already liked.

1. Build item feature vectors: TF-IDF on description + weighted category indicator (`__cat_` prefix, weight 3.0)
2. Pre-compute pairwise item-item cosine similarity; cache invalidates immediately when any item is added
3. For the target user's liked items, look up similar items and score by `Σ item_similarity × user_interaction_weight`
4. **Cold-start fallback:** users with no history receive items ranked by average similarity to all other items (most representative items in the catalog)

**Strength:** new items appear in results as soon as they are added; no cross-user data needed  
**Weakness:** filter bubble — recommends more of the same

---

## A/B Testing Workflow

```
1. POST /ab_tests          → create a test (control=v1, treatment=v2)
2. GET  /ab_tests/{id}/assignments?user_id=X
                           → deterministic hash assigns user to A or B
3. GET  /recommendations/v1 or /v2
                           → serve recommendations for the assigned variant
4. POST /interactions      → log user actions (view / click / purchase)
5. GET  /ab_tests/{id}/results
                           → CTR, conversion rate, engagement time per variant
6. GET  /ab_tests/{id}/statistical_analysis
                           → p-values, confidence intervals, effect sizes, verdict
```

Assignment uses MD5(`"{test_id}:{user_id}"`) so the same user always lands in the same variant, across all servers and restarts.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/interactions` | Log a user interaction |
| GET | `/users/{id}/interactions` | User's interaction history |
| GET | `/items/{id}/stats` | Item popularity counts |
| GET | `/recommendations/v1` | CF recommendations |
| GET | `/recommendations/v2` | Content-based recommendations |
| POST | `/ab_tests` | Create a new A/B test |
| GET | `/ab_tests` | List active tests |
| GET | `/ab_tests/{id}/assignments` | Get or create user variant |
| GET | `/ab_tests/{id}/results` | KPI metrics per variant |
| GET | `/ab_tests/{id}/analysis` | Statistical analysis |
| GET | `/ab_tests/{id}/metrics_over_time` | Metrics bucketed by day/hour |
| GET | `/ab_tests/{id}/statistical_analysis` | Full analysis with conclusions |
| POST | `/seed` | Reset DB and load all sample data |
| POST | `/seed/clear` | Remove all data from the database |

---

## Frontend Demo

A React + Vite dashboard that shows the system live — built for recruiters who want to see it working without reading API docs.

| Tab | What it shows |
|---|---|
| **Overview** | Architecture diagram, tech stack, A/B workflow steps. **Load sample data** / **Clear data** buttons reset or wipe the database instantly — all other pages refresh automatically. |
| **Recommendations** | Pick any user → see CF (v1) and Content-Based (v2) results side by side, log interactions, add items |
| **A/B Tests** | Live CTR/conversion metrics, bar chart comparison, 7-day CTR trend, statistical significance verdict |

The app starts with an empty database. Use **Load sample data** in the Overview tab to populate 50 users, 20 items, and a 7-day A/B test with realistic event history for testing.

---

## Setup

### Docker (recommended — one command)

```bash
docker compose up --build
```

Starts API + Redis + frontend. The database starts empty — use the **Load sample data** button in the Overview tab to populate demo data.

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

```bash
docker compose down          # stop (data persists in ./smart_suggest.db)
docker compose down -v       # stop + wipe volumes
```

### Local

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
# → http://localhost:8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Then open the app and click **Load sample data** in the Overview tab.

---

## Running Tests

```bash
pytest                          # all tests
pytest tests/test_integration.py   # integration only
pytest -v --tb=short            # verbose output
pytest --cov=. --cov-report=term-missing   # with coverage
```

---

## Project Structure

```
smart-suggest/
├── app.py                  ← FastAPI entry point + REST routes
├── config.py               ← categories, strategy configs, DB URL (reads DATABASE_URL env)
├── models.py               ← SQLAlchemy ORM models
├── seed.py                 ← sample data loader (called by POST /seed)
├── entrypoint.sh           ← Docker startup script
├── cache.py                ← in-memory TTL cache (Redis-ready interface)
├── metrics.py              ← pure KPI functions (CTR, conversion, diversity)
├── analysis.py             ← DB-backed metric aggregation
├── significance.py         ← chi-square, Welch's t-test, Wilson CI, power analysis
├── interpretation.py       ← Cohen's h, practical significance, conclusions
│
├── recommenders/
│   ├── cf.py               ← collaborative filtering + cold-item fallback
│   ├── content.py          ← content-based filtering + cold-user fallback
│   └── similarity.py       ← cosine similarity, Pearson, top-K neighbours
│
├── features/
│   └── item_features.py    ← TF-IDF, item-item similarity matrix, TTL cache
│
├── tracking/
│   └── interaction_tracker.py ← log/query user interactions
│
├── ab_testing/
│   ├── manager.py          ← create tests, deterministic variant assignment
│   └── logger.py           ← impression / click / purchase / engagement events
│
├── frontend/               ← React + Vite demo dashboard
│   ├── src/
│   │   ├── pages/
│   │   │   ├── OverviewPage.jsx      ← architecture diagram, tech stack, seed controls
│   │   │   ├── RecommendationsPage.jsx ← CF vs content-based side by side
│   │   │   └── ABTestsPage.jsx       ← live metrics, charts, significance
│   │   └── api.js          ← typed API client (proxies to FastAPI)
│   └── vite.config.js      ← dev proxy → API_URL env var
│
└── tests/
    ├── test_tracking.py
    ├── test_cf.py
    ├── test_content.py
    ├── test_ab_assignment.py
    ├── test_metrics.py
    ├── test_significance.py
    └── test_integration.py
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Cache | In-memory TTL cache (Redis-ready) |
| Stats | Pure Python (no scipy/numpy required) |
| Deploy | Docker + AWS ECS Fargate |
