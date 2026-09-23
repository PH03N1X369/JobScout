"""Job listing sources.

Every fetcher takes (terms, location) and returns a list of normalized job
dicts. Free sources work without configuration; JSearch and Adzuna are enabled
when their API keys are present in the environment.
"""

import hashlib
import html
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

USER_AGENT = "JobScout/1.0 (personal job search tool)"
CACHE_TTL_SECONDS = 30 * 60
CACHE_MAX_ENTRIES = 120
REQUEST_TIMEOUT = 15

_cache = {}
_cache_lock = threading.Lock()


def _get_json(url, params=None, headers=None):
    """GET with a small in-memory cache so repeated searches don't hammer free APIs."""
    key = (url, tuple(sorted((params or {}).items())))
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    resp = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    with _cache_lock:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            # Drop expired entries first, then the oldest, to keep memory bounded.
            for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
                del _cache[k]
            while len(_cache) >= CACHE_MAX_ENTRIES:
                del _cache[next(iter(_cache))]
        _cache[key] = (now + CACHE_TTL_SECONDS, data)
    return data


def _gather(fn, items):
    """Run fn over items in parallel; tolerate partial failure, raise only if all fail."""
    if not items:
        return []
    results, errors = [], []

    def safe(item):
        try:
            return fn(item)
        except Exception as exc:
            errors.append(exc)
            return []

    with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
        for batch in pool.map(safe, items):
            results.extend(batch)
    if errors and len(errors) == len(items):
        raise errors[0]
    return results


# ---------------------------------------------------------------- helpers ---

_BLOCK_TAGS = re.compile(r"<\s*(br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def html_to_text(value, limit=6000):
    if not value:
        return ""
    text = _BLOCK_TAGS.sub(" \n ", str(value))
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    return _WS.sub(" ", text).strip()[:limit]


def to_iso(value):
    """Normalize epoch seconds / ISO strings / 'YYYY-MM-DD HH:MM:SS' to UTC ISO-8601."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            s = str(value).strip().replace("Z", "+00:00")
            if "T" not in s and " " in s:
                s = s.replace(" ", "T", 1)
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_CURRENCY = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "CAD": "CA$", "AUD": "A$"}
_PERIOD = {"year": "/yr", "annual": "/yr", "yearly": "/yr", "hour": "/hr", "hourly": "/hr",
           "month": "/mo", "monthly": "/mo"}


def format_salary(lo, hi, currency="USD", period=None):
    def num(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if v > 0 else None

    lo, hi = num(lo), num(hi)
    if not lo and not hi:
        return None
    code = (currency or "USD").upper()
    sym = _CURRENCY.get(code, f"{code} ")

    def fmt(v):
        return f"{sym}{v / 1000:.0f}k" if v >= 1000 else f"{sym}{v:,.0f}"

    if lo and hi and lo != hi:
        text = f"{fmt(lo)}–{fmt(hi)}"
    else:
        text = fmt(lo or hi)
    return text + _PERIOD.get((period or "").lower(), "")


def make_job(*, source, title, company, url, posted, location="", tags=(), description="",
             salary=None, job_type="", remote=None):
    title = html_to_text(title, 200)
    if not title or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    return {
        "id": hashlib.sha1(f"{source}|{url}".encode()).hexdigest()[:16],
        "title": title,
        "company": html_to_text(company, 120) or "Unknown company",
        "location": (location or "").strip(),
        "url": url,
        "source": source,
        "postedAt": to_iso(posted),
        "tags": [str(t).strip() for t in tags if t and str(t).strip()][:12],
        "description": html_to_text(description),
        "salary": salary or None,
        "jobType": job_type or "",
        "remote": remote,
    }


def _pretty(value):
    return str(value).replace("_", " ").replace("-", " ").strip().capitalize() if value else ""


# ---------------------------------------------------------- free sources ---

def fetch_remoteok(terms, location):
    data = _get_json("https://remoteok.com/api")
    return [make_job(
        source="Remote OK",
        title=j.get("position"),
        company=j.get("company"),
        url=j.get("url"),
        posted=j.get("date") or j.get("epoch"),
        location=j.get("location") or "Remote",
        tags=j.get("tags") or [],
        description=j.get("description"),
        salary=format_salary(j.get("salary_min"), j.get("salary_max"), "USD", "year"),
        remote=True,
    ) for j in data[1:]]  # first element is the API legal notice


def fetch_remotive(terms, location):
    data = _get_json("https://remotive.com/api/remote-jobs")
    return [make_job(
        source="Remotive",
        title=j.get("title"),
        company=j.get("company_name"),
        url=j.get("url"),
        posted=j.get("publication_date"),
        location=j.get("candidate_required_location") or "Remote",
        tags=(j.get("tags") or []) + ([j["category"]] if j.get("category") else []),
        description=j.get("description"),
        salary=j.get("salary") or None,
        job_type=_pretty(j.get("job_type")),
        remote=True,
    ) for j in data.get("jobs", [])]


def fetch_arbeitnow(terms, location):
    def page(n):
        data = _get_json("https://www.arbeitnow.com/api/job-board-api", {"page": n})
        return [make_job(
            source="Arbeitnow",
            title=j.get("title"),
            company=j.get("company_name"),
            url=j.get("url"),
            posted=j.get("created_at"),
            location=j.get("location") or "",
            tags=j.get("tags") or [],
            description=j.get("description"),
            job_type=", ".join((j.get("job_types") or [])[:2]),
            remote=bool(j.get("remote")),
        ) for j in data.get("data", [])]

    return _gather(page, [1, 2])


def fetch_jobicy(terms, location):
    def query(term):
        params = {"count": 50}
        if term:
            params["tag"] = term
        data = _get_json("https://jobicy.com/api/v2/remote-jobs", params)
        return [make_job(
            source="Jobicy",
            title=j.get("jobTitle"),
            company=j.get("companyName"),
            url=j.get("url"),
            posted=j.get("pubDate"),
            location=j.get("jobGeo") or "Remote",
            tags=(j.get("jobIndustry") or []) + ([j["jobLevel"]] if j.get("jobLevel") not in (None, "Any") else []),
            description=j.get("jobDescription") or j.get("jobExcerpt"),
            salary=format_salary(j.get("annualSalaryMin"), j.get("annualSalaryMax"),
                                 j.get("salaryCurrency") or "USD", "year"),
            job_type=", ".join(j.get("jobType") or []),
            remote=True,
        ) for j in data.get("jobs", [])]

    return _gather(query, [None] + list(terms[:4]))  # latest jobs + one tag search per term


def fetch_himalayas(terms, location):
    def query(args):
        term, offset = args
        data = _get_json("https://himalayas.app/jobs/api/search", {"q": term, "limit": 20, "offset": offset})
        jobs = []
        for j in data.get("jobs", []):
            places = j.get("locationRestrictions") or []
            jobs.append(make_job(
                source="Himalayas",
                title=j.get("title"),
                company=j.get("companyName"),
                url=j.get("applicationLink") or j.get("guid"),
                posted=j.get("pubDate"),
                location=(", ".join(places[:3]) + (" +more" if len(places) > 3 else "")) if places else "Worldwide",
                tags=[c.replace("-", " ") for c in (j.get("categories") or [])[:6]],
                description=j.get("description") or j.get("excerpt"),
                salary=format_salary(j.get("minSalary"), j.get("maxSalary"), j.get("currency"), j.get("salaryPeriod")),
                job_type=j.get("employmentType") or "",
                remote=True,
            ))
        return jobs

    return _gather(query, [(t, off) for t in terms[:4] for off in (0, 20)])


# --------------------------------------------------- key-based sources ---

def fetch_jsearch(terms, location):
    """JSearch (RapidAPI) aggregates Google for Jobs: LinkedIn, Indeed, Glassdoor, company sites."""
    headers = {"X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"], "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}

    def query(term):
        data = _get_json("https://jsearch.p.rapidapi.com/search", {
            "query": f"{term} jobs" + (f" in {location}" if location else ""),
            "page": 1,
            "num_pages": 1,
            "date_posted": "month",
            "country": os.environ.get("JSEARCH_COUNTRY", "us"),
        }, headers)
        jobs = []
        for j in data.get("data") or []:
            loc = j.get("job_location") or ", ".join(
                p for p in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if p)
            publisher = j.get("job_publisher")
            jobs.append(make_job(
                source=f"JSearch · {publisher}" if publisher else "JSearch",
                title=j.get("job_title"),
                company=j.get("employer_name"),
                url=j.get("job_apply_link") or j.get("job_google_link"),
                posted=j.get("job_posted_at_datetime_utc") or j.get("job_posted_at_timestamp"),
                location=loc or ("Remote" if j.get("job_is_remote") else ""),
                description=j.get("job_description"),
                salary=format_salary(j.get("job_min_salary"), j.get("job_max_salary"),
                                     j.get("job_salary_currency"), j.get("job_salary_period")),
                job_type=_pretty(j.get("job_employment_type")),
                remote=bool(j.get("job_is_remote")),
            ))
        return jobs

    return _gather(query, list(terms[:2]))  # conserve the free-tier quota


_ADZUNA_CURRENCY = {"gb": "GBP", "in": "INR", "ca": "CAD", "au": "AUD",
                    **{c: "EUR" for c in ("de", "fr", "nl", "it", "es", "at", "be")}}


def fetch_adzuna(terms, location):
    country = os.environ.get("ADZUNA_COUNTRY", "us").lower()
    currency = _ADZUNA_CURRENCY.get(country, "USD")

    def query(term):
        params = {
            "app_id": os.environ["ADZUNA_APP_ID"],
            "app_key": os.environ["ADZUNA_APP_KEY"],
            "results_per_page": 50,
            "what": term,
            "max_days_old": 30,
            "sort_by": "date",
        }
        if location:
            params["where"] = location
        data = _get_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", params)
        jobs = []
        for j in data.get("results", []):
            title = j.get("title") or ""
            jobs.append(make_job(
                source="Adzuna",
                title=title,
                company=(j.get("company") or {}).get("display_name"),
                url=j.get("redirect_url"),
                posted=j.get("created"),
                location=(j.get("location") or {}).get("display_name", ""),
                tags=[(j.get("category") or {}).get("label", "")],
                description=j.get("description"),
                salary=format_salary(j.get("salary_min"), j.get("salary_max"), currency, "year"),
                job_type=_pretty(j.get("contract_time")),
                remote="remote" in title.lower() or None,
            ))
        return jobs

    return _gather(query, list(terms[:3]))


SOURCES = [
    # name, fetcher, homepage, required env vars
    ("Himalayas", fetch_himalayas, "https://himalayas.app/jobs", ()),
    ("Jobicy", fetch_jobicy, "https://jobicy.com", ()),
    ("Remote OK", fetch_remoteok, "https://remoteok.com", ()),
    ("Remotive", fetch_remotive, "https://remotive.com", ()),
    ("Arbeitnow", fetch_arbeitnow, "https://www.arbeitnow.com", ()),
    ("JSearch", fetch_jsearch, "https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch", ("RAPIDAPI_KEY",)),
    ("Adzuna", fetch_adzuna, "https://developer.adzuna.com", ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")),
]


def _enabled(env):
    return all(os.environ.get(v) for v in env)


def source_status():
    return [{"name": name, "homepage": home, "enabled": _enabled(env), "requires": list(env)}
            for name, _, home, env in SOURCES]


def fetch_all(terms, location=""):
    """Query every enabled source in parallel. Returns (jobs, per-source report)."""
    enabled = [(name, fetcher, home) for name, fetcher, home, env in SOURCES if _enabled(env)]

    def run(entry):
        name, fetcher, home = entry
        started = time.time()
        info = {"name": name, "homepage": home, "count": 0, "error": None}
        try:
            jobs = [j for j in fetcher(terms, location) if j]
            info["count"] = len(jobs)
        except Exception as exc:
            jobs = []
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                info["error"] = f"HTTP {exc.response.status_code}"
            elif isinstance(exc, requests.Timeout):
                info["error"] = "timed out"
            else:
                info["error"] = str(exc)[:160] or exc.__class__.__name__
        info["ms"] = int((time.time() - started) * 1000)
        return jobs, info

    with ThreadPoolExecutor(max_workers=max(1, len(enabled))) as pool:
        results = list(pool.map(run, enabled))
    jobs = [j for batch, _ in results for j in batch]
    return jobs, [info for _, info in results]
