"""Populate the database with realistic demo data for the frontend showcase.

Run once from the project root:
    python seed.py
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ab_testing.manager import assign_variant, create_ab_test
from config import DATABASE_URL
from models import ABTestEvent, ActionType, Base, EventType, Item, User, UserInteraction, Variant

random.seed(42)

ENGINE = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=ENGINE)

USERNAMES = [
    "alice", "bob", "charlie", "diana", "eve",
    "frank", "grace", "henry", "iris", "jack",
    *[f"user{i}" for i in range(11, 51)],
]

ITEMS = [
    ("Laptop Pro 15\"", "electronics", "high performance laptop processor SSD display computing device"),
    ("Wireless Noise-Cancelling Headphones", "electronics", "premium audio noise cancelling wireless bluetooth headset"),
    ("Smart Watch Series 5", "electronics", "fitness tracker heart rate GPS smartwatch wearable"),
    ("4K Webcam Pro", "electronics", "HD video conferencing streaming webcam professional camera"),
    ("Mechanical Keyboard RGB", "electronics", "tactile switches RGB backlit gaming typing keyboard"),
    ("Python for Data Science", "books", "python machine learning data analysis pandas numpy scipy"),
    ("Clean Code", "books", "software engineering best practices refactoring code quality"),
    ("Designing Data-Intensive Applications", "books", "databases distributed systems scalability architecture"),
    ("Deep Learning", "books", "neural networks deep learning AI machine learning tensorflow"),
    ("The Pragmatic Programmer", "books", "software development career programming craft skills"),
    ("Premium Cotton T-Shirt", "clothing", "casual comfortable cotton everyday wear soft breathable"),
    ("Running Jacket", "clothing", "lightweight wind-resistant running outdoor athletic jacket"),
    ("Classic Chinos", "clothing", "versatile professional casual pants comfort stretch fabric"),
    ("Yoga Mat Premium", "sports", "non-slip yoga exercise fitness mat cushioned support"),
    ("Adjustable Dumbbells Set", "sports", "home gym weight training strength fitness versatile"),
    ("Resistance Bands Set", "sports", "workout fitness training bands portable gym resistance"),
    ("Air Purifier Pro", "home_appliances", "HEPA filter clean air allergen dust removal home"),
    ("Smart Coffee Maker", "home_appliances", "programmable coffee brewing morning routine smart"),
    ("Protein Powder Vanilla", "health", "whey protein muscle recovery workout supplement amino"),
    ("Vitamin C Face Serum", "beauty", "anti-aging brightening skincare vitamin C glow treatment"),
]

# Interaction clusters so CF finds meaningful neighbours
CLUSTERS = [
    {"users": [1, 2, 3, 4, 5],  "items": list(range(1, 11))},   # tech fans: electronics + books
    {"users": [6, 7, 8],        "items": [14, 15, 16, 19]},      # active: sports + health
    {"users": [9, 10],          "items": [11, 12, 13, 17, 18, 20]},  # lifestyle
]


def seed() -> None:
    Base.metadata.create_all(ENGINE)
    db = Session()

    if db.query(User).count() > 0:
        print("Database already seeded — skipping.")
        db.close()
        return

    print("Seeding …")

    # Users
    for name in USERNAMES:
        db.add(User(username=name))
    db.commit()

    # Items
    for name, category, desc in ITEMS:
        db.add(Item(name=name, category=category, description=desc))
    db.commit()

    # Rich interactions for users 1-10 (powers the recommendation engine)
    action_pool = [ActionType.VIEW, ActionType.VIEW, ActionType.CLICK, ActionType.PURCHASE]
    for cluster in CLUSTERS:
        for uid in cluster["users"]:
            for iid in cluster["items"]:
                if random.random() < 0.75:
                    db.add(UserInteraction(user_id=uid, item_id=iid, action=random.choice(action_pool)))
            # A handful of cross-cluster interactions for diversity
            other = [i for i in range(1, 21) if i not in cluster["items"]]
            for iid in random.sample(other, 3):
                db.add(UserInteraction(user_id=uid, item_id=iid, action=ActionType.VIEW))
    db.commit()

    # A/B test
    test = create_ab_test(db, name="CF-vs-ContentBased-2024", control_variant="v1", treatment_variant="v2")
    print(f"  A/B test created: id={test.id}")

    now = datetime.now(timezone.utc)
    all_item_ids = list(range(1, 21))

    for uid in range(1, 51):
        assignment = assign_variant(db, user_id=uid, test_id=test.id)
        variant: Variant = assignment.variant

        # Variant B (content-based) has a higher CTR — makes stats interesting
        ctr = 0.30 if variant == Variant.A else 0.42
        purchase_rate = 0.12 if variant == Variant.A else 0.18

        shown = random.sample(all_item_ids, min(20, len(all_item_ids)))
        for iid in shown:
            days_ago = random.randint(0, 6)
            ts = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            db.add(ABTestEvent(
                user_id=uid, item_id=iid, test_id=test.id,
                variant=variant, event_type=EventType.IMPRESSION, timestamp=ts,
            ))
            if random.random() < ctr:
                db.add(ABTestEvent(
                    user_id=uid, item_id=iid, test_id=test.id,
                    variant=variant, event_type=EventType.CLICK, timestamp=ts,
                ))
            if random.random() < purchase_rate:
                db.add(ABTestEvent(
                    user_id=uid, item_id=iid, test_id=test.id,
                    variant=variant, event_type=EventType.PURCHASE, timestamp=ts,
                ))
            # Engagement time (attributed to test via assignment join)
            if random.random() < 0.60:
                db.add(ABTestEvent(
                    user_id=uid, item_id=iid, test_id=None,
                    variant=None, event_type=EventType.ENGAGEMENT_TIME,
                    value=round(random.uniform(15.0, 180.0), 1), timestamp=ts,
                ))

    db.commit()
    print(f"  {len(USERNAMES)} users, {len(ITEMS)} items, 1 A/B test with 7-day event history")
    print("Done.")
    db.close()


if __name__ == "__main__":
    seed()
