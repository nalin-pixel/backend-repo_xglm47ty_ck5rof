"""
Database Schemas for Sportex

Each Pydantic model corresponds to a MongoDB collection.
Collection name = lowercase class name.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Core users and roles
class User(BaseModel):
    email: EmailStr
    password_hash: str
    name: str
    role: Literal["athlete", "coach", "organizer", "admin", "guest"] = "athlete"
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    is_active: bool = True
    privacy: Literal["public", "limited", "private"] = "public"

class Athleteprofile(BaseModel):
    user_id: str
    sport: str
    position: Optional[str] = None
    bio: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    stats: dict = Field(default_factory=dict, description="Key-value stats like ppg, apg")
    achievements: List[str] = Field(default_factory=list)
    media: List[dict] = Field(default_factory=list, description="List of {type, url, thumb}")
    recent_performance: List[dict] = Field(default_factory=list, description="[{date, metric, value}]")

class Team(BaseModel):
    name: str
    coach_user_id: str
    sport: str
    location: Optional[str] = None
    roster_user_ids: List[str] = Field(default_factory=list)

class Event(BaseModel):
    title: str
    sport: str
    description: Optional[str] = None
    location: str
    starts_at: datetime
    ends_at: datetime
    capacity: int = 100
    organizer_user_id: str

class Registration(BaseModel):
    event_id: str
    user_id: str
    status: Literal["pending", "confirmed", "waitlisted", "cancelled"] = "pending"

class Notification(BaseModel):
    user_id: str
    type: Literal["invite", "event_update", "system"] = "system"
    title: str
    body: str
    read: bool = False

# Minimal moderation record
class Moderation(BaseModel):
    target_type: Literal["user", "athleteprofile", "team", "event"]
    target_id: str
    action: Literal["approve", "reject", "flag", "suspend"]
    reason: Optional[str] = None
