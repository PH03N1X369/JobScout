# JobScout

A small web app that finds job listings relevant to your resume and keywords, ranks them by fit,
and lets you filter by how recently they were posted (past 24 hours, 3 days, week, 2 weeks, month,
or a custom date range).

## Features

- **Resume upload** (PDF, DOCX, TXT). The resume is parsed in memory and never saved. JobScout pulls
  out your skills and likely job titles, shown as chips you can switch on or off.
- **Keywords** that you type. These count the most in ranking. Known terms expand to their
  synonyms, so `javascript` also matches `JS` and `node.js` matches `nodejs`.
- **Live listings** from several job APIs queried in parallel, merged, de-duplicated, and ranked.
  Each result shows *why* it matched (keywords, role match, skills).
- **Date filter** with counts next to each option. Filtering happens in the browser, so it's
  instant. There's also a custom from/to range.
- **Other filters:** remote only, sources, and free-text filtering of the results. Sort by best
  match or newest.
- **Job board links** that open LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs and Dice
  with your query and date window already applied, for listings the APIs don't cover.

## Setup

Requires Python 3.9+.

```bash
cd jobscout
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000.

## Deploy to Render (public link)

The repo includes a [`render.yaml`](render.yaml) Blueprint for Render's free tier.

1. Push this folder to a new GitHub repository. `app.py` must be at the repository root.
2. Sign in at [dashboard.render.com](https://dashboard.render.com) and choose **New → Blueprint**.
3. Connect GitHub if asked, then pick the repository. Render reads `render.yaml`.
4. Render asks for the optional API keys. Leave them blank or paste your JSearch/Adzuna keys.
   Then click **Apply** (or **Deploy Blueprint**).
5. When the build finishes (about 2–3 minutes), your public URL appears at the top of the service
   page, e.g. `https://jobscout-xxxx.onrender.com`.

Every push to the repo redeploys automatically. On the free tier the service sleeps after about
15 minutes without traffic, so the first visit after that takes about 30–60 seconds to wake it up.

The public app limits each visitor to 12 searches and 10 uploads per minute so nobody can use
your server to flood the free job APIs. Change the limits in `app.py`.

## Job sources

Works out of the box with these free, keyless APIs:

| Source    | Coverage                                  | How it's queried                |
|-----------|-------------------------------------------|---------------------------------|
| Himalayas | Remote jobs, global                       | Keyword search                  |
| Jobicy    | Remote jobs                               | Tag search + latest 50          |
| Remote OK | Remote jobs, mostly tech                  | Latest feed (~100)              |
| Remotive  | Remote jobs                               | Latest feed (small sample)      |
| Arbeitnow | Jobs in Europe (mainly Germany), incl. on-site | Latest ~500               |

The free sources lean toward **remote** and **tech** roles. For broad coverage, including on-site
jobs from LinkedIn, Indeed, Glassdoor and company career pages, add one or both optional keys.
Copy `.env.example` to `.env` and fill in:

- **JSearch** (`RAPIDAPI_KEY`): aggregates Google for Jobs. Free tier on
  [RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch). Set `JSEARCH_COUNTRY` (default `us`).
- **Adzuna** (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`): free developer keys at
  [developer.adzuna.com](https://developer.adzuna.com). Set `ADZUNA_COUNTRY` (e.g. `us`, `gb`, `in`).

Restart the server after editing `.env`. API responses are cached in memory for 30 minutes, so
repeat searches are fast and don't overload the free APIs.

Please respect each API's terms. They ask that listings link back to the original posting and
credit the source, which JobScout does on every result.

## How ranking works

Each listing gets three signals, each scored from 0 to 1:

1. **Keywords** (50%): each keyword scores highest when it's in the job title, less in the tags,
   and less again in the description.
2. **Skills** (30%): how many of your selected resume skills the posting mentions. The score levels
   off as matches add up, so one posting doesn't win just by listing everything.
3. **Role** (20%): whether the job title matches a role detected in your resume.

Signals you didn't provide are dropped and the rest reweighted. The final score becomes a
*Strong / Good / Partial match* label (hover it to see the number). Duplicate postings found on
several boards are merged.

## Project layout

```
app.py            Flask routes: /api/parse-resume, /api/search, /api/sources
resume_parser.py  PDF / DOCX / TXT text extraction
skills.py         Skill and job-title vocabularies and matching rules
sources.py        One fetcher per job API, response normalization, caching
ranking.py        Relevance scoring, de-duplication, snippets
static/           Frontend (vanilla HTML/CSS/JS, no build step)
```

To teach JobScout new skills or titles, add entries to `SKILLS` / `TITLES` in `skills.py`.
To add a job source, write a `fetch_*` function in `sources.py` and add it to `SOURCES`.

## Limitations

- Scanned (image-only) PDFs have no text to extract. Use a text-based PDF or DOCX. Legacy `.doc`
  isn't supported.
- Skill detection is dictionary based. Unusual skills won't be detected automatically, so add them
  as keywords.
- Job boards change their URL parameters from time to time, so a board link may open without the
  date filter applied. The URL builders are in `BOARDS` in `static/app.js`.
- The Indeed link uses `indeed.com`. For another country, change it to that country's Indeed site
  (e.g. `in.indeed.com`, `uk.indeed.com`).
