"""JobScout: find relevant job listings from a resume and keywords."""

import os
import threading
import time
from collections import deque
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from locations import resolve  # noqa: E402
from ranking import pick_search_terms, rank_jobs  # noqa: E402
from resume_parser import ResumeParseError, extract_text  # noqa: E402
from skills import canonical_skill, canonical_title, extract_skills, extract_titles  # noqa: E402
from sources import ADZUNA_COUNTRIES, fetch_all, source_status  # noqa: E402

MAX_UPLOAD_MB = 5

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
# Hosts like Render sit behind one proxy that appends the real client IP to
# X-Forwarded-For; trust exactly that hop so rate limits apply per visitor.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("Content-Security-Policy", CSP)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


class RateLimiter:
    """Sliding-window limit per client IP, kept in memory (fine for one instance)."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.hits = {}
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self.lock:
            if len(self.hits) > 5000:  # drop idle clients so memory stays bounded
                self.hits = {k: q for k, q in self.hits.items() if q and q[-1] > now - self.window}
            q = self.hits.setdefault(key, deque())
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def rate_limited(limiter, message):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not limiter.allow(request.remote_addr or "unknown"):
                return jsonify(error=message), 429
            return view(*args, **kwargs)
        return wrapper
    return decorator


search_limiter = RateLimiter(limit=12, window_seconds=60)
upload_limiter = RateLimiter(limit=10, window_seconds=60)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.get("/api/sources")
def sources():
    return jsonify(source_status())


@app.post("/api/parse-resume")
@rate_limited(upload_limiter, "Too many uploads. Wait a minute and try again.")
def parse_resume():
    upload = request.files.get("resume")
    if not upload or not upload.filename:
        return jsonify(error="No file uploaded."), 400
    try:
        # Parsed in memory only; the file is never written to disk.
        text = extract_text(upload.filename, upload.read())
    except ResumeParseError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(
        filename=upload.filename,
        characters=len(text),
        skills=extract_skills(text)[:40],
        titles=extract_titles(text),
    )


def _clean_list(value, limit):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip() and len(item) <= 80:
            out.append(item.strip())
    return out[:limit]


@app.post("/api/search")
@rate_limited(search_limiter, "Too many searches. Wait a minute and try again.")
def search():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    keywords = _clean_list(body.get("keywords"), 10)
    skills = [canonical_skill(s) or s for s in _clean_list(body.get("skills"), 40)]
    titles = [canonical_title(t) or t for t in _clean_list(body.get("titles"), 5)]
    location = body.get("location")
    place = resolve(location[:100] if isinstance(location, str) else "")

    if not (keywords or skills or titles):
        return jsonify(error="Upload a resume or enter at least one keyword."), 400

    terms = pick_search_terms(keywords, titles, skills)
    raw, report = fetch_all(terms, place)
    jobs = rank_jobs(raw, keywords, skills, titles, place)
    return jsonify(terms=terms, total=len(jobs), scanned=len(raw), sources=report, jobs=jobs,
                   location=place.to_dict(), tip=_coverage_tip(place, jobs))


def _coverage_tip(place, jobs):
    """Explain thin local results: the keyless sources are mostly remote-job boards."""
    if place.kind not in ("city", "country", "unknown"):
        return None
    if sum(1 for j in jobs if j["locationMatch"] == "local") >= 5:
        return None
    enabled = {s["name"] for s in source_status() if s["enabled"]}
    if {"Adzuna", "JSearch"} & enabled:
        return None
    keys = ["Adzuna", "JSearch"] if not place.country or place.country.lower() in ADZUNA_COUNTRIES else ["JSearch"]
    return (f"Few on-site jobs in {place.label} come from the free sources, which mostly list remote roles. "
            f"Use the job board links for local listings, or add a free {' or '.join(keys)} API key "
            f"(see README) to include them here.")


@app.get("/api/location")
def location_lookup():
    return jsonify(resolve(request.args.get("q", "")[:100]).to_dict())


@app.errorhandler(413)
def too_large(_):
    return jsonify(error=f"File is too large (max {MAX_UPLOAD_MB} MB)."), 413


if __name__ == "__main__":
    # Local development server. In production (e.g. Render) gunicorn serves `app`.
    port = int(os.environ.get("PORT", 5000))
    print(f" * JobScout running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1", threaded=True)
