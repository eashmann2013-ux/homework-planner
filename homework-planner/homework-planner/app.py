import time
import datetime
from flask import Flask, jsonify, render_template

from scraper import scrape_all

app = Flask(__name__)

# Small server-side cache so a burst of page loads doesn't hammer the
# teacher sites with repeat requests. Refreshes automatically after 5 minutes.
_cache = {"data": None, "fetched_at": 0}
CACHE_SECONDS = 5 * 60


def get_homework(force=False):
    now = time.time()
    if force or _cache["data"] is None or (now - _cache["fetched_at"]) > CACHE_SECONDS:
        _cache["data"] = scrape_all()
        _cache["fetched_at"] = now
    return _cache["data"], _cache["fetched_at"]


@app.route("/")
def index():
    return render_template("index.html", today=datetime.date.today().isoformat())


@app.route("/api/homework")
def api_homework():
    data, fetched_at = get_homework()
    return jsonify({
        "homework": data,
        "fetched_at": datetime.datetime.fromtimestamp(fetched_at).isoformat(),
        "today": datetime.date.today().isoformat(),
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    data, fetched_at = get_homework(force=True)
    return jsonify({
        "homework": data,
        "fetched_at": datetime.datetime.fromtimestamp(fetched_at).isoformat(),
        "today": datetime.date.today().isoformat(),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
