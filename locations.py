"""Resolve a typed location and decide which job postings are available there.

A search for "Bengaluru" should return jobs based in Bengaluru plus remote
jobs that accept candidates in India, and drop remote jobs limited to other
countries ("Remote - US only").
"""

import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Optional

APAC = ["apac", "asia pacific", "asia-pacific", "asia"]
EUROPE = ["europe", "eu", "eea", "emea"]
MIDDLE_EAST = ["middle east", "mena", "gcc", "emea"]
AFRICA = ["africa", "emea"]
NORTH_AMERICA = ["north america", "americas"]
LATAM = ["latam", "latin america", "south america", "americas"]
OCEANIA = ["oceania", "anz", "apac", "asia pacific", "asia-pacific"]

# code: (name, aliases, regions whose remote jobs accept this country)
COUNTRIES = {
    "IN": ("India", ["india", "bharat"], APAC + ["south asia"]),
    "US": ("United States", ["united states", "united states of america", "usa", "u.s.a.", "u.s.", "us"], NORTH_AMERICA),
    "GB": ("United Kingdom", ["united kingdom", "uk", "u.k.", "great britain", "britain", "england", "scotland", "wales"], EUROPE),
    "CA": ("Canada", ["canada"], NORTH_AMERICA),
    "DE": ("Germany", ["germany", "deutschland"], EUROPE + ["dach"]),
    "AT": ("Austria", ["austria", "österreich"], EUROPE + ["dach"]),
    "CH": ("Switzerland", ["switzerland", "schweiz", "suisse"], EUROPE + ["dach"]),
    "NL": ("Netherlands", ["netherlands", "the netherlands", "holland"], EUROPE + ["benelux"]),
    "BE": ("Belgium", ["belgium"], EUROPE + ["benelux"]),
    "FR": ("France", ["france"], EUROPE),
    "ES": ("Spain", ["spain", "españa"], EUROPE),
    "PT": ("Portugal", ["portugal"], EUROPE),
    "IT": ("Italy", ["italy", "italia"], EUROPE),
    "IE": ("Ireland", ["ireland"], EUROPE),
    "PL": ("Poland", ["poland", "polska"], EUROPE),
    "SE": ("Sweden", ["sweden"], EUROPE + ["nordics"]),
    "DK": ("Denmark", ["denmark"], EUROPE + ["nordics"]),
    "NO": ("Norway", ["norway"], EUROPE + ["nordics"]),
    "FI": ("Finland", ["finland"], EUROPE + ["nordics"]),
    "AU": ("Australia", ["australia"], OCEANIA),
    "NZ": ("New Zealand", ["new zealand"], OCEANIA),
    "SG": ("Singapore", ["singapore"], APAC + ["southeast asia"]),
    "MY": ("Malaysia", ["malaysia"], APAC + ["southeast asia"]),
    "PH": ("Philippines", ["philippines"], APAC + ["southeast asia"]),
    "ID": ("Indonesia", ["indonesia"], APAC + ["southeast asia"]),
    "JP": ("Japan", ["japan"], APAC),
    "PK": ("Pakistan", ["pakistan"], APAC + ["south asia"]),
    "BD": ("Bangladesh", ["bangladesh"], APAC + ["south asia"]),
    "LK": ("Sri Lanka", ["sri lanka"], APAC + ["south asia"]),
    "AE": ("United Arab Emirates", ["united arab emirates", "uae"], MIDDLE_EAST),
    "SA": ("Saudi Arabia", ["saudi arabia", "ksa"], MIDDLE_EAST),
    "EG": ("Egypt", ["egypt"], MIDDLE_EAST + AFRICA),
    "ZA": ("South Africa", ["south africa"], AFRICA),
    "NG": ("Nigeria", ["nigeria"], AFRICA),
    "KE": ("Kenya", ["kenya"], AFRICA),
    "BR": ("Brazil", ["brazil", "brasil"], LATAM),
    "MX": ("Mexico", ["mexico", "méxico"], LATAM + ["north america"]),
    "AR": ("Argentina", ["argentina"], LATAM),
    "CO": ("Colombia", ["colombia"], LATAM),
}

# canonical city: (country code, aliases)
CITIES = {
    "Bengaluru": ("IN", ["bengaluru", "bangalore", "blr"]),
    "Mumbai": ("IN", ["mumbai", "bombay", "navi mumbai", "thane"]),
    "Delhi NCR": ("IN", ["delhi ncr", "new delhi", "delhi", "ncr", "gurugram", "gurgaon", "noida", "greater noida",
                         "faridabad", "ghaziabad"]),
    "Hyderabad": ("IN", ["hyderabad", "secunderabad"]),
    "Chennai": ("IN", ["chennai", "madras"]),
    "Pune": ("IN", ["pune"]),
    "Kolkata": ("IN", ["kolkata", "calcutta"]),
    "Ahmedabad": ("IN", ["ahmedabad", "gandhinagar"]),
    "Kochi": ("IN", ["kochi", "cochin", "ernakulam"]),
    "Jaipur": ("IN", ["jaipur"]),
    "Chandigarh": ("IN", ["chandigarh", "mohali", "panchkula"]),
    "Coimbatore": ("IN", ["coimbatore"]),
    "Indore": ("IN", ["indore"]),
    "Thiruvananthapuram": ("IN", ["thiruvananthapuram", "trivandrum"]),
    "Mysuru": ("IN", ["mysuru", "mysore"]),
    "Lucknow": ("IN", ["lucknow"]),
    "Bhubaneswar": ("IN", ["bhubaneswar"]),
    "Nagpur": ("IN", ["nagpur"]),
    "Vadodara": ("IN", ["vadodara", "baroda"]),
    "Visakhapatnam": ("IN", ["visakhapatnam", "vizag"]),
    "Surat": ("IN", ["surat"]),
    "New York": ("US", ["new york", "nyc", "manhattan", "brooklyn"]),
    "San Francisco Bay Area": ("US", ["san francisco", "bay area", "san jose", "palo alto", "mountain view",
                                      "oakland", "sunnyvale"]),
    "Los Angeles": ("US", ["los angeles"]),
    "Seattle": ("US", ["seattle", "bellevue", "redmond"]),
    "Austin": ("US", ["austin"]),
    "Boston": ("US", ["boston", "cambridge, ma"]),
    "Chicago": ("US", ["chicago"]),
    "Denver": ("US", ["denver", "boulder"]),
    "Atlanta": ("US", ["atlanta"]),
    "Dallas": ("US", ["dallas", "fort worth"]),
    "Houston": ("US", ["houston"]),
    "Miami": ("US", ["miami"]),
    "Washington, DC": ("US", ["washington, dc", "washington dc", "washington d.c."]),
    "Philadelphia": ("US", ["philadelphia"]),
    "San Diego": ("US", ["san diego"]),
    "London": ("GB", ["london"]),
    "Manchester": ("GB", ["manchester"]),
    "Edinburgh": ("GB", ["edinburgh"]),
    "Birmingham": ("GB", ["birmingham"]),
    "Bristol": ("GB", ["bristol"]),
    "Toronto": ("CA", ["toronto"]),
    "Vancouver": ("CA", ["vancouver"]),
    "Montreal": ("CA", ["montreal", "montréal"]),
    "Berlin": ("DE", ["berlin"]),
    "Munich": ("DE", ["munich", "münchen", "muenchen"]),
    "Hamburg": ("DE", ["hamburg"]),
    "Frankfurt": ("DE", ["frankfurt"]),
    "Cologne": ("DE", ["cologne", "köln", "koeln"]),
    "Stuttgart": ("DE", ["stuttgart"]),
    "Düsseldorf": ("DE", ["düsseldorf", "dusseldorf", "duesseldorf"]),
    "Vienna": ("AT", ["vienna", "wien"]),
    "Zurich": ("CH", ["zurich", "zürich"]),
    "Amsterdam": ("NL", ["amsterdam"]),
    "Paris": ("FR", ["paris"]),
    "Madrid": ("ES", ["madrid"]),
    "Barcelona": ("ES", ["barcelona"]),
    "Lisbon": ("PT", ["lisbon", "lisboa"]),
    "Milan": ("IT", ["milan", "milano"]),
    "Dublin": ("IE", ["dublin"]),
    "Warsaw": ("PL", ["warsaw", "warszawa"]),
    "Stockholm": ("SE", ["stockholm"]),
    "Copenhagen": ("DK", ["copenhagen"]),
    "Sydney": ("AU", ["sydney"]),
    "Melbourne": ("AU", ["melbourne"]),
    "Auckland": ("NZ", ["auckland"]),
    "Dubai": ("AE", ["dubai"]),
    "Abu Dhabi": ("AE", ["abu dhabi"]),
    "Kuala Lumpur": ("MY", ["kuala lumpur"]),
    "Manila": ("PH", ["manila", "makati"]),
    "Tokyo": ("JP", ["tokyo"]),
    "Cape Town": ("ZA", ["cape town"]),
    "Johannesburg": ("ZA", ["johannesburg"]),
    "Lagos": ("NG", ["lagos"]),
    "Nairobi": ("KE", ["nairobi"]),
    "São Paulo": ("BR", ["são paulo", "sao paulo"]),
    "Mexico City": ("MX", ["mexico city", "cdmx"]),
    "Buenos Aires": ("AR", ["buenos aires"]),
}

REMOTE_WORDS = {"remote", "anywhere", "worldwide", "work from home", "wfh"}
ANYWHERE = re.compile(r"(?<![a-z])(anywhere|worldwide|global|globally|international|world ?wide)(?![a-z])")
# Words that say nothing about *where* a remote job is available.
FILLER = re.compile(r"(?<![a-z])(remote|fully|100%|work from home|wfh|hybrid|flexible|only|based|first|friendly|"
                    r"timezone|time zone|hours|and|or|in|the)(?![a-z])|[^a-z]+")


def _union(aliases):
    alts = sorted({a.lower() for a in aliases}, key=len, reverse=True)
    return re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z])")


@dataclass(frozen=True)
class Place:
    raw: str
    kind: str                 # none | remote | city | country | unknown
    label: str                # what to show: "Bengaluru", "India", "Remote"
    city: Optional[str] = None
    country: Optional[str] = None       # ISO 3166 alpha-2
    country_name: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def resolve(raw):
    text = (raw or "").strip()
    if not text:
        return Place(raw="", kind="none", label="")
    low = text.lower()
    if low in REMOTE_WORDS:
        return Place(raw=text, kind="remote", label="Remote")

    for part in [p.strip() for p in low.split(",")] + [low]:
        for city, (code, aliases) in CITIES.items():
            if part in aliases or part == city.lower():
                return Place(raw=text, kind="city", label=city, city=city, country=code,
                             country_name=COUNTRIES[code][0])
    for part in [p.strip() for p in low.split(",")][::-1] + [low]:
        for code, (name, aliases, _) in COUNTRIES.items():
            if part in aliases or part == name.lower():
                return Place(raw=text, kind="country", label=name, country=code, country_name=name)
    return Place(raw=text, kind="unknown", label=text)


@lru_cache(maxsize=256)
def _matchers(place):
    city_re = None
    if place.kind == "city":
        city_re = _union(CITIES[place.city][1] + [place.city])
    elif place.kind == "country":
        # "Pune" is in India even when a posting doesn't say "India".
        aliases = [a for city, (code, names) in CITIES.items() if code == place.country for a in names + [city]]
        city_re = _union(aliases) if aliases else None
    elif place.kind == "unknown":
        city_re = _union([place.raw])
    country_re = region_re = None
    if place.country:
        name, aliases, regions = COUNTRIES[place.country]
        country_re = _union(aliases + [name])
        region_re = _union(regions)
    return city_re, country_re, region_re


def is_remote(job):
    return job.get("remote") is True or bool(re.search(r"(?<![a-z])remote(?![a-z])", (job.get("location") or "").lower()))


def classify(job, place):
    """'local' (based in the place), 'remote' (remote and open to the place), or None."""
    text = (job.get("_where") or job.get("location") or "").lower()
    remote = is_remote(job)
    if place.kind == "remote":
        return "remote" if remote else None

    if job.get("_near") and not remote:
        return "local"  # the source itself searched this place
    city_re, country_re, region_re = _matchers(place)
    if city_re and city_re.search(text):
        return "local"
    if place.kind == "country" and not remote and country_re.search(text):
        return "local"
    if not remote:
        return None

    # A remote job: available unless it names places that exclude this one.
    if country_re and country_re.search(text):
        return "remote"
    if region_re and region_re.search(text):
        return "remote"
    if ANYWHERE.search(text) or not FILLER.sub("", text):
        return "remote"
    return None
