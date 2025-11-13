import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import db, create_document
from schemas import (
    User as UserSchema,
    Athleteprofile as AthleteProfileSchema,
    Team as TeamSchema,
    Event as EventSchema,
    Registration as RegistrationSchema,
    Notification as NotificationSchema,
    Moderation as ModerationSchema,
)

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Sportex API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility helpers
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "athlete"


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class ProfilePayload(BaseModel):
    sport: str
    position: Optional[str] = None
    bio: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    stats: Dict[str, Any] = {}
    achievements: List[str] = []
    media: List[Dict[str, Any]] = []


# Auth dependencies
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db["user"].find_one({"id": user_id}) or db["user"].find_one({"_id": user_id})
        if not user:
            email = payload.get("email")
            if email:
                user = db["user"].find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token decode error")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authorization header")


@app.get("/")
def root():
    return {"message": "Sportex API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response


# Auth endpoints
@app.post("/auth/register", response_model=Token)
def register(payload: RegisterPayload):
    existing = db["user"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserSchema(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
    )
    user_dict = user.model_dump()
    user_dict["id"] = create_document("user", user)
    token = create_access_token({"sub": user_dict["id"], "email": user.email, "role": user.role})
    return Token(access_token=token)


@app.post("/auth/login", response_model=Token)
def login(payload: LoginPayload):
    user = db["user"].find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token({"sub": user.get("id") or str(user.get("_id")), "email": user["email"], "role": user.get("role", "athlete")})
    return Token(access_token=token)


@app.get("/me")
def me(current=Depends(get_current_user)):
    safe = {k: v for k, v in current.items() if k not in ("password_hash",)}
    return safe


# Athlete profiles
@app.post("/athletes/me")
def upsert_athlete_profile(data: ProfilePayload, current=Depends(get_current_user)):
    user_id = current.get("id") or str(current.get("_id"))
    existing = db["athleteprofile"].find_one({"user_id": user_id})
    payload = AthleteProfileSchema(user_id=user_id, **data.model_dump()).model_dump()
    now = datetime.now(timezone.utc)
    payload.update({"updated_at": now})
    if existing:
        db["athleteprofile"].update_one({"_id": existing["_id"]}, {"$set": payload})
        doc = db["athleteprofile"].find_one({"_id": existing["_id"]})
    else:
        new_id = create_document("athleteprofile", payload)
        doc = db["athleteprofile"].find_one({"id": new_id}) or {**payload, "id": new_id}
    return doc


@app.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: str, current=Depends(get_current_user)):
    doc = db["athleteprofile"].find_one({"id": athlete_id}) or db["athleteprofile"].find_one({"_id": athlete_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Athlete not found")
    # Privacy: if private and not owner/admin, limit fields
    owner_id = doc.get("user_id")
    owner = db["user"].find_one({"id": owner_id}) or {}
    privacy = owner.get("privacy", "public")
    if privacy == "private" and (current.get("id") != owner_id) and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Profile is private")
    if privacy == "limited" and (current.get("id") != owner_id) and current.get("role") != "admin":
        doc = {k: doc[k] for k in ["sport", "position", "stats", "achievements", "media"] if k in doc}
    return doc


@app.get("/athletes")
def list_athletes(
    sport: Optional[str] = None,
    position: Optional[str] = None,
    location: Optional[str] = None,
    min_stat_key: Optional[str] = Query(None, description="e.g., ppg"),
    min_stat_value: Optional[float] = Query(None),
    page: int = 1,
    page_size: int = 20,
):
    q: Dict[str, Any] = {}
    if sport:
        q["sport"] = sport
    if position:
        q["position"] = position
    if location:
        # based on user location
        user_ids = [u.get("id") or str(u.get("_id")) for u in db["user"].find({"location": location})]
        q["user_id"] = {"$in": user_ids}
    cursor = db["athleteprofile"].find(q)
    if min_stat_key is not None and min_stat_value is not None:
        cursor = filter(lambda d: float(d.get("stats", {}).get(min_stat_key, -1)) >= float(min_stat_value), cursor)
        docs = list(cursor)
    else:
        docs = list(cursor)
    total = len(docs)
    start = (page - 1) * page_size
    end = start + page_size
    return {"results": docs[start:end], "total": total, "page": page, "page_size": page_size}


# Teams
class TeamCreate(BaseModel):
    name: str
    sport: str
    location: Optional[str] = None


@app.post("/teams")
def create_team(payload: TeamCreate, current=Depends(get_current_user)):
    if current.get("role") not in ("coach", "organizer", "admin"):
        raise HTTPException(status_code=403, detail="Only coaches/organizers can create teams")
    team = TeamSchema(name=payload.name, coach_user_id=current.get("id"), sport=payload.sport, location=payload.location)
    team_id = create_document("team", team)
    doc = db["team"].find_one({"id": team_id}) or {**team.model_dump(), "id": team_id}
    return doc


@app.get("/teams/{team_id}")
def get_team(team_id: str):
    doc = db["team"].find_one({"id": team_id}) or db["team"].find_one({"_id": team_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Team not found")
    return doc


@app.post("/teams/{team_id}/add")
def add_to_roster(team_id: str, user_id: str, current=Depends(get_current_user)):
    team = db["team"].find_one({"id": team_id})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if current.get("role") not in ("coach", "admin") or team.get("coach_user_id") != current.get("id"):
        raise HTTPException(status_code=403, detail="Only coach can modify roster")
    roster = team.get("roster_user_ids", [])
    if user_id not in roster:
        roster.append(user_id)
        db["team"].update_one({"id": team_id}, {"$set": {"roster_user_ids": roster}})
        notif = NotificationSchema(user_id=user_id, type="invite", title="Team Invite", body=f"You were added to {team['name']}")
        create_document("notification", notif)
    return {"ok": True, "roster": roster}


# Events
class EventCreate(BaseModel):
    title: str
    sport: str
    description: Optional[str] = None
    location: str
    starts_at: datetime
    ends_at: datetime
    capacity: int = 100


@app.post("/events")
def create_event(payload: EventCreate, current=Depends(get_current_user)):
    if current.get("role") not in ("organizer", "coach", "admin"):
        raise HTTPException(status_code=403, detail="Only organizers/coaches can create events")
    evt = EventSchema(
        title=payload.title,
        sport=payload.sport,
        description=payload.description,
        location=payload.location,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
        organizer_user_id=current.get("id"),
    )
    eid = create_document("event", evt)
    doc = db["event"].find_one({"id": eid}) or {**evt.model_dump(), "id": eid}
    return doc


@app.get("/events")
def list_events(sport: Optional[str] = None, page: int = 1, page_size: int = 20):
    q: Dict[str, Any] = {}
    if sport:
        q["sport"] = sport
    docs = list(db["event"].find(q))
    total = len(docs)
    start = (page - 1) * page_size
    end = start + page_size
    return {"results": docs[start:end], "total": total, "page": page, "page_size": page_size}


@app.get("/events/{event_id}")
def get_event(event_id: str):
    doc = db["event"].find_one({"id": event_id}) or db["event"].find_one({"_id": event_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    return doc


# Registration
@app.post("/events/{event_id}/register")
def register_event(event_id: str, current=Depends(get_current_user)):
    evt = db["event"].find_one({"id": event_id})
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")
    existing = db["registration"].find_one({"event_id": event_id, "user_id": current.get("id")})
    if existing:
        return existing
    count = db["registration"].count_documents({"event_id": event_id, "status": {"$in": ["pending", "confirmed"]}})
    status = "confirmed" if count < int(evt.get("capacity", 100)) else "waitlisted"
    reg = RegistrationSchema(event_id=event_id, user_id=current.get("id"), status=status)
    rid = create_document("registration", reg)
    notif = NotificationSchema(user_id=evt.get("organizer_user_id"), type="event_update", title="New Registration", body=f"New registration for {evt['title']}")
    create_document("notification", notif)
    return db["registration"].find_one({"id": rid}) or {**reg.model_dump(), "id": rid}


# Dashboards
@app.get("/dashboard/coach")
def coach_dashboard(current=Depends(get_current_user)):
    if current.get("role") not in ("coach", "admin"):
        raise HTTPException(status_code=403, detail="Only coaches")
    teams = list(db["team"].find({"coach_user_id": current.get("id")}))
    regs = list(db["registration"].find({}))
    events = list(db["event"].find({"organizer_user_id": current.get("id")}))
    return {
        "teams": teams,
        "events": events,
        "registrations": regs,
    }


# Notifications
@app.get("/notifications")
def my_notifications(current=Depends(get_current_user)):
    notifs = list(db["notification"].find({"user_id": current.get("id")}))
    return {"results": notifs}


@app.post("/notifications/{notif_id}/read")
def mark_read(notif_id: str, current=Depends(get_current_user)):
    db["notification"].update_one({"id": notif_id}, {"$set": {"read": True}})
    return {"ok": True}


# Admin
@app.get("/admin/overview")
def admin_overview(current=Depends(get_current_user)):
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return {
        "users": db["user"].count_documents({}),
        "athletes": db["athleteprofile"].count_documents({}),
        "teams": db["team"].count_documents({}),
        "events": db["event"].count_documents({}),
        "registrations": db["registration"].count_documents({}),
    }


@app.post("/admin/moderate")
def moderate(action: ModerationSchema, current=Depends(get_current_user)):
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    create_document("moderation", action)
    return {"ok": True}


# Seed data endpoint
@app.post("/seed")
def seed():
    if db["user"].count_documents({}) > 0:
        return {"message": "Already seeded"}
    # Create admin, coach, organizer, and 10 athletes
    admin_id = create_document("user", UserSchema(email="admin@sportex.io", password_hash=hash_password("admin123"), name="Admin", role="admin"))
    coach_id = create_document("user", UserSchema(email="coach@sportex.io", password_hash=hash_password("coach123"), name="Coach Carla", role="coach", location="Austin, TX"))
    org_id = create_document("user", UserSchema(email="org@sportex.io", password_hash=hash_password("org123"), name="Org Omar", role="organizer", location="Dallas, TX"))

    # 10 athletes
    sports = ["basketball", "soccer", "track", "volleyball"]
    athletes = []
    for i in range(10):
        uid = create_document("user", UserSchema(email=f"athlete{i+1}@sportex.io", password_hash=hash_password("pass1234"), name=f"Athlete {i+1}", role="athlete", location="Austin, TX"))
        prof = AthleteProfileSchema(
            user_id=uid,
            sport=sports[i % len(sports)],
            position=["G", "F", "M", "S"][i % 4],
            bio="Aspiring athlete ready to compete.",
            stats={"ppg": round(8 + i * 0.7, 1), "apg": round(2 + i * 0.3, 1)},
            achievements=["All-County", "MVP Nominee"] if i % 2 == 0 else ["All-Conference"],
            media=[{"type": "image", "url": "https://placehold.co/600x400", "thumb": "https://placehold.co/300x200"}],
            recent_performance=[{"date": (datetime.now(timezone.utc) - timedelta(days=d)).date().isoformat(), "metric": "ppg", "value": round(6 + (i % 5) + d*0.2, 1)} for d in range(5)]
        )
        create_document("athleteprofile", prof)
        athletes.append(uid)

    # One team by coach
    team_id = create_document("team", TeamSchema(name="Austin Hawks", coach_user_id=coach_id, sport="basketball", location="Austin, TX"))

    # Two events by organizer
    now = datetime.now(timezone.utc)
    e1 = create_document("event", EventSchema(title="Spring Showcase", sport="basketball", description="Open run for scouts", location="Austin, TX", starts_at=now + timedelta(days=7), ends_at=now + timedelta(days=7, hours=3), capacity=50, organizer_user_id=org_id))
    e2 = create_document("event", EventSchema(title="Summer Combine", sport="soccer", description="Drills and scrimmages", location="Dallas, TX", starts_at=now + timedelta(days=21), ends_at=now + timedelta(days=21, hours=4), capacity=80, organizer_user_id=org_id))

    # Add first 5 athletes to team and register first 3 to first event
    roster = athletes[:5]
    db["team"].update_one({"id": team_id}, {"$set": {"roster_user_ids": roster}})
    for uid in athletes[:3]:
        create_document("registration", RegistrationSchema(event_id=e1, user_id=uid, status="confirmed"))

    return {"message": "Seeded", "admin_id": admin_id, "coach_id": coach_id, "organizer_id": org_id, "team_id": team_id, "event_ids": [e1, e2]}


# OpenAPI will serve as our Postman collection
