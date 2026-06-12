from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cf_recommender import get_cf_recommendations
from config import DATABASE_URL
from interaction_tracker import (
    get_item_popularity,
    get_user_history,
    get_user_profile,
    log_interaction,
)
from models import ActionType, Base

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
