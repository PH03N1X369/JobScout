"""Score job postings against the user's keywords and resume profile.

Three signals, each in [0, 1]:
  keywords - how strongly the user's own keywords appear (title > tags > description)
  skills   - how many resume skills the posting asks for (saturating)
  title    - whether the posting's title matches the candidate's likely role
Signals that the user didn't provide are left out and the rest re-weighted.
"""

import math
import re

from skills import keyword_regex, skill_field_regexes, title_regex, title_tokens

TITLE_W, TAGS_W, DESC_W = 1.0, 0.75, 0.45
SIGNAL_WEIGHTS = {"keywords": 0.5, "skills": 0.3, "title": 0.2}
MIN_SCORE = 0.2
SNIPPET_LEN = 260


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _field_score(regex, title, tags, desc):
    if regex.search(title):
        return TITLE_W
    if regex.search(tags):
        return TAGS_W
    if regex.search(desc):
        return DESC_W
    return 0.0


def _keyword_score(keyword, regex, token_regexes, title, tags, desc):
    score = _field_score(regex, title, tags, desc)
    if score or len(token_regexes) < 2:
        return score
    # Multi-word keyword that doesn't appear verbatim ("senior python developer"):
    # give partial credit when (nearly) all of its words show up.
    hits = [_field_score(r, title, tags, desc) for r in token_regexes]
    missing = sum(1 for h in hits if not h)
    if missing > (1 if len(hits) >= 3 else 0):
        return 0.0
    return 0.5 * (1 - missing / len(hits)) * max(hits)


def _title_score(resume_titles, job_title):
    best = 0.0
    job_tokens = set(title_tokens(job_title))
    for name in resume_titles:
        if title_regex(name).search(job_title):
            return 1.0
        wanted = title_tokens(name)
        if wanted and job_tokens:
            overlap = sum(1 for t in wanted if t in job_tokens) / len(wanted)
            if overlap >= 0.5:
                best = max(best, 0.6 * overlap)
    return best


def _snippet(desc, regexes):
    start = 0
    for r in regexes:
        m = r.search(desc)
        if m:
            start = max(0, m.start() - 90)
            break
    if start:
        space = desc.find(" ", start)
        start = space + 1 if 0 <= space < start + 20 else start
    text = desc[start:start + SNIPPET_LEN].strip()
    if start:
        text = "…" + text
    if start + SNIPPET_LEN < len(desc):
        text = text.rsplit(" ", 1)[0] + "…"
    return text


def rank_jobs(jobs, keywords, skills, titles, limit=400):
    keywords = [k for k in keywords if k.strip()]
    kw_rules = []
    for k in keywords:
        tokens = [t for t in re.findall(r"[\w+#.]+", k) if len(t) > 1]
        kw_rules.append((k, keyword_regex(k), [keyword_regex(t) for t in tokens] if len(tokens) > 1 else []))
    skill_rules = [(s, skill_field_regexes(s)) for s in skills]

    active = {name: w for name, w in SIGNAL_WEIGHTS.items()
              if (name == "keywords" and keywords) or (name == "skills" and skills) or (name == "title" and titles)}
    total_weight = sum(active.values()) or 1.0

    seen = {}
    for job in jobs:
        title, desc = job["title"], job["description"]
        tags = " , ".join(job["tags"])

        kw_hits, kw_total = [], 0.0
        for k, regex, token_res in kw_rules:
            s = _keyword_score(k, regex, token_res, title, tags, desc)
            if s:
                kw_hits.append(k)
                kw_total += s
        kw_score = kw_total / len(kw_rules) if kw_rules else 0.0

        skill_hits, skill_sum = [], 0.0
        for name, (title_re, tags_re, desc_re) in skill_rules:
            if title_re.search(title) or tags_re.search(tags):
                skill_hits.append(name)
                skill_sum += 1.0
            elif desc_re.search(desc):
                skill_hits.append(name)
                skill_sum += 0.5
        skill_score = 1 - math.exp(-skill_sum / 3)

        t_score = _title_score(titles, title) if titles else 0.0

        if keywords:
            keep = kw_score > 0 or (t_score >= 0.6 and len(skill_hits) >= 2)
        else:
            keep = t_score >= 0.6 or len(skill_hits) >= 2
        if not keep:
            continue

        signals = {"keywords": kw_score, "skills": skill_score, "title": t_score}
        score = sum(signals[n] * w for n, w in active.items()) / total_weight
        if score < MIN_SCORE:
            continue

        out = {k: v for k, v in job.items() if k != "description"}
        out.update({
            "score": round(score, 3),
            "match": "strong" if score >= 0.55 else "good" if score >= 0.35 else "partial",
            "matched": {
                "keywords": kw_hits,
                "skills": [s for s in skill_hits if s.lower() not in {k.lower() for k in kw_hits}][:8],
                "title": t_score >= 0.6,
            },
            "snippet": _snippet(desc, [r for _, r, _ in kw_rules] + [rs[2] for _, rs in skill_rules]),
        })

        # The same posting often appears on several boards; keep the best-scoring copy.
        key = _norm(job["title"]) + "|" + _norm(job["company"])
        if key not in seen or seen[key]["score"] < out["score"]:
            seen[key] = out

    # Newest first, then a stable sort by score so ties stay newest-first.
    ranked = sorted(seen.values(), key=lambda j: j["postedAt"] or "", reverse=True)
    ranked.sort(key=lambda j: -j["score"])
    return ranked[:limit]


def pick_search_terms(keywords, titles, skills, limit=5):
    """Terms sent to the job APIs: user keywords first, then likely titles, then top skills."""
    terms, seen = [], set()
    for t in list(keywords) + list(titles[:2]) + list(skills[:3]):
        key = t.strip().lower()
        if key and key not in seen:
            seen.add(key)
            terms.append(t.strip())
    return terms[:limit]
