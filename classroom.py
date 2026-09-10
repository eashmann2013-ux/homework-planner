"""
classroom.py
Handles talking to the Google Classroom API once a student has connected
their account. Two things live here:

1. OAuth helpers (build_flow, credentials_to_dict / credentials_from_dict)
   used by the /connect-classroom and /oauth2callback routes in app.py.
2. fetch_classroom_homework(credentials) — pulls current coursework
   assigned to the logged-in student and turns it into the same entry
   shape the other scrapers use.

Nothing here is cached globally, because credentials are per-visitor
(stored in their browser session), not shared across everyone who opens
the site.
"""

import os
import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleAuthRequest

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
]

CLIENT_ID = os.environ.get("CLASSROOM_CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLASSROOM_CLIENT_SECRET")


def is_configured():
    """True once CLASSROOM_CLIENT_ID / CLASSROOM_CLIENT_SECRET are set as
    environment variables (see README for how to get these from Google)."""
    return bool(CLIENT_ID and CLIENT_SECRET)


def build_flow(redirect_uri):
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    return flow


def credentials_to_dict(creds):
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def credentials_from_dict(data):
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )


def _due_date_to_iso(coursework):
    """Classroom returns dueDate as {year, month, day} and dueTime separately
    (or omits both if there's no due date). Combine into a plain ISO date."""
    due = coursework.get("dueDate")
    if not due:
        return None
    try:
        return datetime.date(due["year"], due["month"], due["day"]).isoformat()
    except (KeyError, ValueError):
        return None


def _posted_date_to_iso(coursework):
    created = coursework.get("creationTime")  # RFC3339 timestamp, e.g. "2026-09-02T15:04:05.000Z"
    if not created:
        return None
    try:
        return datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def fetch_classroom_homework(creds_dict):
    """Returns (entries, refreshed_creds_dict_or_None, error_message_or_None).
    refreshed_creds_dict is returned when the access token had to be refreshed,
    so the caller can save the new one back into the session."""
    creds = credentials_from_dict(creds_dict)
    refreshed = None

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            refreshed = credentials_to_dict(creds)
        except Exception as e:
            return [], None, f"Your Google Classroom connection expired and couldn't refresh ({e}). Try reconnecting."

    try:
        service = build("classroom", "v1", credentials=creds)
        courses_resp = service.courses().list(courseStates=["ACTIVE"], studentId="me").execute()
        courses = courses_resp.get("courses", [])

        entries = []
        for course in courses:
            course_name = course.get("name", "Untitled course")
            work_resp = service.courses().courseWork().list(
                courseId=course["id"], courseWorkStates=["PUBLISHED"], orderBy="dueDate desc"
            ).execute()
            for cw in work_resp.get("courseWork", []):
                title = cw.get("title", "Untitled assignment")
                description = (cw.get("description") or "").strip()
                text = f"[{course_name}] {title}"
                if description:
                    snippet = description if len(description) < 140 else description[:137] + "..."
                    text += f" — {snippet}"
                entries.append({
                    "subject": "google_classroom",
                    "date": _due_date_to_iso(cw),
                    "posted": _posted_date_to_iso(cw),
                    "text": text,
                    "source": cw.get("alternateLink", "https://classroom.google.com"),
                })
        return entries, refreshed, None

    except Exception as e:
        return [], refreshed, f"Couldn't load Google Classroom homework ({e})."
