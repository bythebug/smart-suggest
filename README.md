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

### Version A — Collaborative Filtering (v1)

**Idea:** users who agreed in the past will agree in the future.

1. Build a weighted user-item interaction matrix (view=1, click=3, purchase=5)
2. Compute pairwise cosine similarity between users
3. Find the top-K nearest neighbours for the target user
4. Collect items those neighbours liked that the target user hasn't seen
5. Score candidates by `Σ similarity × neighbour_weight` and return top-N

**Strength:** discovers unexpected items through shared taste communities  
**Weakness:** cold start for new users; invisible to new items

### Version B — Content-Based Filtering (v2)

**Idea:** recommend items similar to what this user has already liked.

1. Build item feature vectors: TF-IDF on description + weighted category indicator
2. Pre-compute pairwise item-item cosine similarity (cached with 1-hour TTL)
3. For the target user's liked items, look up similar items
4. Score by `Σ item_similarity × user_interaction_weight`

**Strength:** works for new items immediately; no cross-user data needed  
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

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the API
uvicorn app:app --reload

# 4. Interactive docs
open http://localhost:8000/docs
```

### Docker

```bash
docker compose up        # starts API + Redis
docker compose down -v   # stop and remove volumes
```

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
├── app.py                  ← FastAPI entry point
├── config.py               ← categories, strategy configs, DB URL
├── models.py               ← SQLAlchemy ORM models
├── schema.sql              ← reference DDL (indexes, constraints)
├── cache.py                ← in-memory TTL cache (Redis-ready interface)
├── metrics.py              ← pure KPI functions (CTR, conversion, diversity)
├── analysis.py             ← DB-backed metric aggregation
├── significance.py         ← chi-square, Welch's t-test, Wilson CI, power analysis
├── interpretation.py       ← Cohen's h, practical significance, conclusions
│
├── recommenders/
│   ├── cf.py               ← user-based collaborative filtering
│   ├── content.py          ← content-based filtering
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
