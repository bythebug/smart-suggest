from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ab_testing.logger import log_click, log_impression, log_purchase
from ab_testing.manager import assign_variant, create_ab_test
from analysis import _engagement_times, aggregate_by_time, calculate_metrics_by_variant, get_statistical_analysis
from interpretation import analyze_ab_test
from recommenders.cf import get_cf_recommendations
from recommenders.content import get_content_recommendations
from config import DATABASE_URL
from tracking.interaction_tracker import (
    get_item_popularity,
    get_user_history,
    get_user_profile,
    log_interaction,
)
from models import ABTest, ABTestEvent, ActionType, Base, Item, TestStatus, User, Variant

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Smart Suggest API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ABTestRequest(BaseModel):
    name: str
    control: str = "v1"
    treatment: str = "v2"


class InteractionRequest(BaseModel):
    user_id: int
    item_id: int
    action: ActionType


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    item_id: int
    action: ActionType
    timestamp: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post(
    "/interactions",
    status_code=status.HTTP_201_CREATED,
    summary="Log a user interaction",
)
def create_interaction(
    body: InteractionRequest,
    db: Session = Depends(get_db),
):
    try:
        interaction = log_interaction(db, body.user_id, body.item_id, body.action)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user_id or item_id — referenced record does not exist.",
        )
    return {
        "id": interaction.id,
        "user_id": interaction.user_id,
        "item_id": interaction.item_id,
        "action": interaction.action,
        "timestamp": interaction.timestamp.isoformat(),
    }


@app.get(
    "/users/{user_id}/interactions",
    summary="Fetch a user's interaction history",
)
def user_interactions(
    user_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    history = get_user_history(db, user_id, limit=limit)
    return [
        {
            "id": i.id,
            "item_id": i.item_id,
            "action": i.action,
            "timestamp": i.timestamp.isoformat(),
        }
        for i in history
    ]


@app.get(
    "/items/{item_id}/stats",
    summary="Get item popularity counts broken down by action",
)
def item_stats(item_id: int, db: Session = Depends(get_db)):
    return get_item_popularity(db, item_id)


@app.get(
    "/recommendations/v1",
    summary="User-based collaborative filtering recommendations",
)
def recommendations_v1(
    user_id: int,
    count: int = 5,
    db: Session = Depends(get_db),
):
    recs = get_cf_recommendations(db, user_id=user_id, n=count)
    return {"user_id": user_id, "strategy": "v1", "recommendations": recs}


@app.get(
    "/recommendations/v2",
    summary="Content-based filtering recommendations",
)
def recommendations_v2(
    user_id: int,
    count: int = 5,
    db: Session = Depends(get_db),
):
    recs = get_content_recommendations(db, user_id=user_id, n=count)
    return {"user_id": user_id, "strategy": "v2", "recommendations": recs}


# ---------------------------------------------------------------------------
# A/B test management
# ---------------------------------------------------------------------------


@app.post(
    "/ab_tests",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new A/B test",
)
def create_test(body: ABTestRequest, db: Session = Depends(get_db)):
    try:
        test = create_ab_test(
            db,
            name=body.name,
            control_variant=body.control,
            treatment_variant=body.treatment,
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A test named {body.name!r} already exists.",
        )
    return {
        "id": test.id,
        "name": test.name,
        "status": test.status,
        "control": test.control_strategy,
        "treatment": test.treatment_strategy,
        "created_at": test.created_at.isoformat(),
    }


@app.get("/ab_tests", summary="List all active A/B tests")
def list_tests(db: Session = Depends(get_db)):
    tests = db.query(ABTest).filter(ABTest.status == TestStatus.ACTIVE).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "control": t.control_strategy,
            "treatment": t.treatment_strategy,
            "created_at": t.created_at.isoformat(),
        }
        for t in tests
    ]


@app.get(
    "/ab_tests/{test_id}/assignments",
    summary="Get (or lazily create) a user's variant assignment for a test",
)
def get_assignment(test_id: int, user_id: int, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test {test_id} not found.",
        )

    assignment = assign_variant(db, user_id=user_id, test_id=test_id)
    return {
        "test_id": test_id,
        "user_id": user_id,
        "variant": assignment.variant,
        "assigned_at": assignment.created_at.isoformat(),
    }


@app.get(
    "/ab_tests/{test_id}/results",
    summary="CTR, conversion rate, and engagement metrics for both variants",
)
def ab_test_results(test_id: int, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")
    return calculate_metrics_by_variant(db, test_id)


@app.get(
    "/ab_tests/{test_id}/analysis",
    summary="Statistical analysis comparing variant A vs B",
)
def ab_test_analysis(test_id: int, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")
    return get_statistical_analysis(db, test_id)


@app.get(
    "/ab_tests/{test_id}/metrics_over_time",
    summary="Impressions, clicks, and CTR bucketed by day or hour",
)
def ab_test_metrics_over_time(
    test_id: int,
    period: str = "day",
    db: Session = Depends(get_db),
):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")
    try:
        return aggregate_by_time(db, test_id, period=period)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@app.get(
    "/ab_tests/{test_id}/statistical_analysis",
    summary="Full statistical analysis: p-values, CIs, effect sizes, and conclusions",
)
def ab_test_statistical_analysis(test_id: int, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")
    metrics = calculate_metrics_by_variant(db, test_id)
    eng = _engagement_times(db, test_id)
    return analyze_ab_test(metrics, eng_times_a=eng["A"], eng_times_b=eng["B"])


@app.post(
    "/ab_tests/{test_id}/simulate",
    summary="Generate synthetic event data for a test (demo use)",
)
def simulate_test_data(test_id: int, db: Session = Depends(get_db)):
    import random as _random
    _random.seed()

    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")

    existing = db.query(ABTestEvent).filter(ABTestEvent.test_id == test_id).count()
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This test already has event data.",
        )

    users = db.query(User).all()
    items = db.query(Item).all()
    if not users or not items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No users or items in DB.")

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)

    for user in users[:50]:
        assignment = assign_variant(db, user_id=user.id, test_id=test_id)
        variant = assignment.variant
        ctr = 0.30 if variant == Variant.A else 0.42
        purchase_rate = 0.12 if variant == Variant.A else 0.18

        shown = _random.sample(items, min(20, len(items)))
        for item in shown:
            ts = now - timedelta(days=_random.randint(0, 6), hours=_random.randint(0, 23))
            log_impression(db, user.id, item.id, test_id, variant)
            if _random.random() < ctr:
                log_click(db, user.id, item.id, test_id, variant)
            if _random.random() < purchase_rate:
                log_purchase(db, user.id, item.id, test_id, variant)

    return {"simulated": True, "test_id": test_id, "users": min(50, len(users))}


class EventRequest(BaseModel):
    user_id: int
    item_id: int
    event_type: str  # impression | click | purchase


@app.post(
    "/ab_tests/{test_id}/events",
    status_code=status.HTTP_201_CREATED,
    summary="Log a single A/B test event for a user",
)
def log_test_event(test_id: int, body: EventRequest, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test {test_id} not found.")
    if body.event_type not in ("impression", "click", "purchase"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="event_type must be impression, click, or purchase.")

    assignment = assign_variant(db, user_id=body.user_id, test_id=test_id)
    variant = assignment.variant

    if body.event_type == "impression":
        log_impression(db, body.user_id, body.item_id, test_id, variant)
    elif body.event_type == "click":
        log_click(db, body.user_id, body.item_id, test_id, variant)
    else:
        log_purchase(db, body.user_id, body.item_id, test_id, variant)

    return {"user_id": body.user_id, "item_id": body.item_id, "event": body.event_type, "variant": variant.value}


@app.get("/users", summary="List all users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return [{"id": u.id, "username": u.username} for u in users]


@app.get("/items", summary="List all items")
def list_items(db: Session = Depends(get_db)):
    items = db.query(Item).order_by(Item.id).all()
    return [
        {"id": i.id, "name": i.name, "category": i.category, "description": i.description}
        for i in items
    ]
