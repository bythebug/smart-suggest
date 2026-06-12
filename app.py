from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ab_test_manager import assign_variant, create_ab_test
from cf_recommender import get_cf_recommendations
from content_recommender import get_content_recommendations
from config import DATABASE_URL
from interaction_tracker import (
    get_item_popularity,
    get_user_history,
    get_user_profile,
    log_interaction,
)
from models import ABTest, ActionType, Base, TestStatus

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
