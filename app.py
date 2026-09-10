import os
import time
import datetime
from flask import Flask, jsonify, render_template, session, redirect, request, url_for

import teachers
from scraper import fetch_homework_for_teacher
import classroom

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me-in-production")

# Cache per teacher id, since different visitors can pick different teachers.
# Keyed by teacher id -> {"data": [...], "fetched_at": timestamp}
_cache = {}
CACHE_SECONDS = 5 * 60


def get_homework_for_teacher_id(teacher_id, force=False):
    teacher = teachers.by_id(teacher_id)
    if not teacher:
        return [], time.time()

    now = time.time()
    cached = _cache.get(teacher_id)
    if force or cached is None or (now - cached["fetched_at"]) > CACHE_SECONDS:
        data = fetch_homework_for_teacher(teacher)
        _cache[teacher_id] = {"data": data, "fetched_at": now}
        return data, now
    return cached["data"], cached["fetched_at"]


def _redirect_uri():
    return url_for("oauth2callback", _external=True)


@app.route("/")
def index():
    return render_template(
        "index.html",
        today=datetime.date.today().isoformat(),
        classroom_configured=classroom.is_configured(),
    )


@app.route("/api/teachers")
def api_teachers():
    return jsonify(teachers.all_grouped())


@app.route("/api/homework")
def api_homework():
    return _homework_response(force=False)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    return _homework_response(force=True)


def _homework_response(force):
    selected = {
        "math": request.args.get("math_teacher", ""),
        "science": request.args.get("science_teacher", ""),
        "language_arts": request.args.get("language_arts_teacher", ""),
    }

    homework = {}
    latest_fetch = 0
    for subject, teacher_id in selected.items():
        if not teacher_id:
            homework[subject] = []
            continue
        entries, fetched_at = get_homework_for_teacher_id(teacher_id, force=force)
        homework[subject] = entries
        latest_fetch = max(latest_fetch, fetched_at)

    classroom_connected = "classroom_credentials" in session
    classroom_error = None
    if classroom_connected:
        entries, refreshed, error = classroom.fetch_classroom_homework(session["classroom_credentials"])
        if refreshed:
            session["classroom_credentials"] = refreshed
        homework["google_classroom"] = entries
        classroom_error = error
    else:
        homework["google_classroom"] = []

    return jsonify({
        "homework": homework,
        "fetched_at": datetime.datetime.fromtimestamp(latest_fetch).isoformat() if latest_fetch else None,
        "today": datetime.date.today().isoformat(),
        "classroom_connected": classroom_connected,
        "classroom_configured": classroom.is_configured(),
        "classroom_error": classroom_error,
    })


@app.route("/connect-classroom")
def connect_classroom():
    if not classroom.is_configured():
        return "Google Classroom isn't set up on this server yet (missing CLASSROOM_CLIENT_ID / CLASSROOM_CLIENT_SECRET).", 500
    flow = classroom.build_flow(_redirect_uri())
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    if not classroom.is_configured():
        return "Google Classroom isn't set up on this server yet.", 500
    flow = classroom.build_flow(_redirect_uri())
    flow.fetch_token(authorization_response=request.url)
    session["classroom_credentials"] = classroom.credentials_to_dict(flow.credentials)
    return redirect(url_for("index", tab="google_classroom"))


@app.route("/disconnect-classroom", methods=["POST"])
def disconnect_classroom():
    session.pop("classroom_credentials", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
