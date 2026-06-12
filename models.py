from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ActionType(str, Enum):
    VIEW = "view"
    CLICK = "click"
    PURCHASE = "purchase"


class RecommendationStrategy(str, Enum):
    V1 = "v1"
    V2 = "v2"


class TestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Variant(str, Enum):
    A = "A"
    B = "B"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interactions = relationship("UserInteraction", back_populates="user")
    recommendations = relationship("Recommendation", back_populates="user")
    ab_test_assignments = relationship("ABTestAssignment", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(1000))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interactions = relationship("UserInteraction", back_populates="item")
    recommendations = relationship("Recommendation", back_populates="item")

    def __repr__(self) -> str:
        return f"<Item id={self.id} name={self.name!r} category={self.category!r}>"


class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    action = Column(SAEnum(ActionType), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="interactions")
    item = relationship("Item", back_populates="interactions")

    def __repr__(self) -> str:
        return f"<UserInteraction user_id={self.user_id} item_id={self.item_id} action={self.action}>"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    strategy = Column(SAEnum(RecommendationStrategy), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="recommendations")
    item = relationship("Item", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<Recommendation user_id={self.user_id} item_id={self.item_id} strategy={self.strategy}>"


class ABTest(Base):
    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    status = Column(SAEnum(TestStatus), default=TestStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    assignments = relationship("ABTestAssignment", back_populates="test")
    results = relationship("ABTestResult", back_populates="test")

    def __repr__(self) -> str:
        return f"<ABTest id={self.id} name={self.name!r} status={self.status}>"


class ABTestAssignment(Base):
    __tablename__ = "ab_test_assignments"
    __table_args__ = (
        # Each user is assigned to a given test exactly once.
        UniqueConstraint("test_id", "user_id", name="uq_assignment_test_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    variant = Column(SAEnum(Variant), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    test = relationship("ABTest", back_populates="assignments")
    user = relationship("User", back_populates="ab_test_assignments")

    def __repr__(self) -> str:
        return f"<ABTestAssignment test_id={self.test_id} user_id={self.user_id} variant={self.variant}>"


class ABTestResult(Base):
    __tablename__ = "ab_test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    variant = Column(SAEnum(Variant), nullable=False)
    value = Column(Float, nullable=False)

    test = relationship("ABTest", back_populates="results")

    def __repr__(self) -> str:
        return (
            f"<ABTestResult test_id={self.test_id} metric={self.metric_name!r} "
            f"variant={self.variant} value={self.value}>"
        )
