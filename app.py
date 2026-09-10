import os
import time
import datetime
from flask import Flask, jsonify, render_template, session, redirect, request, url_for

from scraper import scrape_all
import classroom

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me-in-production")

# Small server-side cache for the three scraped sites (these are the same
# for every visitor, so one shared cache is fine). Classroom data is NOT
# cached here since it's different per person and lives in their session.
_cache = {"data": None, "fetched_at": 0}
CACHE_SECONDS = 5 * 60


def get_scraped_homework(force=False):
    now = time.time()
    if force or _cache["data"] is None or (now - _cache["fetched_at"]) > CACHE_SECONDS:
        _cache["data"] = scrape_all()
        _cache["fetched_at"] = now
    return _cache["data"], _cache["fetched_at"]


def _redirect_uri():
    # Built from the current request so this works on localhost AND once deployed,
    # without hardcoding a URL anywhere in the code.
    return url_for("oauth2callback", _external=True)


@app.route("/")
def index():
    return render_template(
        "index.html",
        today=datetime.date.today().isoformat(),
        classroom_configured=classroom.is_configured(),
    )


@app.route("/api/homework")
def api_homework():
    return _homework_response(force=False)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    return _homework_response(force=True)


def _homework_response(force):
    data, fetched_at = get_scraped_homework(force=force)
    homework = dict(data)  # copy so we don't mutate the shared cache

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
        "fetched_at": datetime.datetime.fromtimestamp(fetched_at).isoformat(),
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
