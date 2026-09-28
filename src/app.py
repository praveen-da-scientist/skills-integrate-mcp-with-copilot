"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import hashlib
import hmac
import json
import secrets
import time
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")
teacher_credentials_file = Path(os.getenv(
    "TEACHER_CREDENTIALS_FILE", str(current_dir / "teachers.json")
))
session_cookie_name = "teacher_session"
session_duration_seconds = 8 * 60 * 60
password_hash_iterations = 310_000
teacher_sessions: dict[str, tuple[str, float]] = {}


class TeacherLogin(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, password_hash_iterations
    )
    return f"pbkdf2_sha256${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, salt_hex, expected_hash = stored_hash.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, password_hash_iterations
    )
    return hmac.compare_digest(actual, expected)


def load_teacher_credentials() -> dict[str, str]:
    if not teacher_credentials_file.exists():
        return {}

    credentials = json.loads(teacher_credentials_file.read_text(encoding="utf-8"))
    if not isinstance(credentials, dict) or any(
        not isinstance(username, str) or not isinstance(password_hash, str)
        for username, password_hash in credentials.items()
    ):
        raise RuntimeError("Teacher credentials must map usernames to password hashes")
    return credentials


def require_teacher(
    teacher_session: str | None = Cookie(default=None, alias=session_cookie_name),
) -> str:
    session = teacher_sessions.get(teacher_session or "")
    if session is None or session[1] <= time.time():
        if teacher_session:
            teacher_sessions.pop(teacher_session, None)
        raise HTTPException(status_code=401, detail="Teacher sign-in required")
    return session[0]

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(credentials: TeacherLogin, request: Request, response: Response):
    teacher_credentials = load_teacher_credentials()
    stored_hash = teacher_credentials.get(credentials.username)
    if not stored_hash or not verify_password(credentials.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    now = time.time()
    for token, (_, expires_at) in list(teacher_sessions.items()):
        if expires_at <= now:
            teacher_sessions.pop(token, None)

    token = secrets.token_urlsafe(32)
    teacher_sessions[token] = (
        credentials.username, now + session_duration_seconds
    )
    response.set_cookie(
        key=session_cookie_name,
        value=token,
        max_age=session_duration_seconds,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"username": credentials.username}


@app.get("/auth/session")
def get_teacher_session(current_teacher: str = Depends(require_teacher)):
    return {"username": current_teacher}


@app.post("/auth/logout")
def logout(
    response: Response,
    teacher_session: str | None = Cookie(default=None, alias=session_cookie_name),
):
    if teacher_session:
        teacher_sessions.pop(teacher_session, None)
    response.delete_cookie(key=session_cookie_name, path="/")
    return {"message": "Signed out"}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str,
    current_teacher: str = Depends(require_teacher),
):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    current_teacher: str = Depends(require_teacher),
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
