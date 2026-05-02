"""
Local job posting parser using spaCy NER + regex heuristics.
No API key required. Falls back gracefully if spaCy is unavailable.
"""

import re
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# spaCy — optional, loaded once
# ---------------------------------------------------------------------------

_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False  # mark as unavailable
    return _nlp if _nlp else None


# ---------------------------------------------------------------------------
# Salary
# ---------------------------------------------------------------------------

_SALARY_RE = re.compile(
    r"""
    (?:
        \$[\d,]+(?:\.\d+)?[kK]?          # $80,000 / $80k
        (?:\s*[-–—to]+\s*
            \$[\d,]+(?:\.\d+)?[kK]?      # – $100k
        )?
    )
    (?:\s*(?:per\s+)?(?:year|yr|hour|hr|/hr|/year|annually))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Also catch "80,000 - 100,000" style (without $)
_SALARY_PLAIN_RE = re.compile(
    r'\b(\d{2,3}[,.]?\d{3})\s*[-–—]\s*(\d{2,3}[,.]?\d{3})\b'
)

def extract_salary(text: str) -> str:
    m = _SALARY_RE.search(text)
    if m:
        raw = m.group(0).strip()
        # Normalise spacing around dash
        raw = re.sub(r'\s*[-–—]\s*', '–', raw)
        return raw

    m = _SALARY_PLAIN_RE.search(text)
    if m:
        lo, hi = m.group(1), m.group(2)
        # Only treat as salary if values look like annual income
        lo_val = int(lo.replace(',', '').replace('.', ''))
        hi_val = int(hi.replace(',', '').replace('.', ''))
        if 20000 <= lo_val <= 500000 and lo_val < hi_val:
            return f"${lo}–${hi}"

    return ""


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

# US states abbreviations
_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN',
    'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
    'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
    'TX','UT','VT','VA','WA','WV','WI','WY','DC',
}

# Patterns like "Austin, TX" or "New York, NY" or "San Francisco, California"
_CITY_STATE_RE = re.compile(
    r'\b([A-Z][a-zA-Z\s]{2,20}),\s*([A-Z]{2}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b'
)

# "Remote", "Hybrid", "On-site / Onsite"
_WORK_TYPE_RE = re.compile(
    r'\b(remote|hybrid|on[\s-]?site|in[\s-]?office|work from home|wfh)\b',
    re.IGNORECASE,
)

# Location label hints in the text
_LOCATION_LABEL_RE = re.compile(
    r'(?:location|office|based in|located in|work location)[:\s]+([^\n\.]{3,60})',
    re.IGNORECASE,
)

def extract_location(text: str, nlp=None) -> str:
    # 1. Check for labelled location field
    m = _LOCATION_LABEL_RE.search(text)
    if m:
        candidate = m.group(1).strip().split('\n')[0].strip(' ,;')
        if 3 < len(candidate) < 60:
            return candidate

    # 2. Detect work-type keywords
    wt = _WORK_TYPE_RE.search(text)

    # 3. spaCy GPE (geo-political entity)
    gpe = ""
    if nlp:
        doc = nlp(text[:3000])
        gpes = [ent.text for ent in doc.ents if ent.label_ == "GPE"]
        if gpes:
            # Prefer the first one that looks like a city (not a country alone)
            gpe = gpes[0]

    # 4. Regex city/state fallback
    city_state = ""
    for m in _CITY_STATE_RE.finditer(text):
        city, state = m.group(1).strip(), m.group(2).strip()
        if state.upper() in _STATES or len(state) > 3:
            city_state = f"{city}, {state}"
            break

    location_parts = []
    if wt:
        label = wt.group(1).title()
        if label.lower() in ('wfh', 'work from home'):
            label = 'Remote'
        location_parts.append(label)

    place = city_state or gpe
    if place:
        location_parts.append(place)

    return " – ".join(location_parts) if location_parts else ""


# ---------------------------------------------------------------------------
# Company name
# ---------------------------------------------------------------------------

# Common job board URL patterns
_BOARD_COMPANY_RE = {
    'greenhouse.io':  re.compile(r'greenhouse\.io/([^/]+)'),
    'lever.co':       re.compile(r'jobs\.lever\.co/([^/]+)'),
    'ashbyhq.com':    re.compile(r'jobs\.ashbyhq\.com/([^/]+)'),
    'workday.com':    re.compile(r'([^.]+)\.wd\d+\.myworkdayjobs\.com'),
    'smartrecruiters': re.compile(r'jobs\.smartrecruiters\.com/([^/]+)'),
    'icims.com':      re.compile(r'([^.]+)\.icims\.com'),
    'jobvite.com':    re.compile(r'jobs\.jobvite\.com/([^/]+)'),
}

_COMPANY_LABEL_RE = re.compile(
    r'(?:^|\n)(?:company|employer|about\s+us|about)[:\s]+([^\n]{2,60})',
    re.IGNORECASE,
)

def extract_company(text: str, url: str, nlp=None) -> str:
    # 1. Known job board URL slug
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    for board, pattern in _BOARD_COMPANY_RE.items():
        if board in host:
            m = pattern.search(url)
            if m:
                slug = m.group(1)
                # Convert slug to title case words
                return re.sub(r'[-_]', ' ', slug).title()

    # 2. Labelled field in text
    m = _COMPANY_LABEL_RE.search(text)
    if m:
        candidate = m.group(1).strip().split('\n')[0].strip(' ,;')
        if 2 < len(candidate) < 60:
            return candidate

    # 3. spaCy ORG entities
    if nlp:
        doc = nlp(text[:2000])
        orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        if orgs:
            return orgs[0]

    # 4. Infer from domain
    domain_parts = host.replace('www.', '').split('.')
    if domain_parts:
        return domain_parts[0].title()

    return ""


# ---------------------------------------------------------------------------
# Job title / role
# ---------------------------------------------------------------------------

_ROLE_LABEL_RE = re.compile(
    r'(?:^|\n)(?:job title|position|role|title)[:\s]+([^\n]{3,80})',
    re.IGNORECASE,
)

# Common title patterns — look for these in the first ~500 chars
_TITLE_KEYWORDS = [
    r'(?:senior|sr\.?|junior|jr\.?|lead|staff|principal|associate)?\s*'
    r'(?:software|frontend|backend|full[\s-]?stack|data|security|cyber|'
    r'network|cloud|devops|platform|mobile|embedded|machine\s+learning|ml|ai|'
    r'systems|site\s+reliability|sre|qa|quality)\s+'
    r'(?:engineer|developer|architect|analyst|scientist|specialist|'
    r'administrator|consultant|manager|director|officer|intern)',

    r'(?:cybersecurity|information\s+security|infosec|vulnerability|threat|'
    r'penetration|pen\s+test|grc|governance|compliance|risk)\s*'
    r'(?:analyst|engineer|specialist|consultant|manager|intern|officer)?',

    r'(?:product|project|program|engineering|it|technical|operations)\s+'
    r'(?:manager|director|lead|coordinator)',
]

_TITLE_RE = re.compile(
    '|'.join(f'(?:{p})' for p in _TITLE_KEYWORDS),
    re.IGNORECASE,
)

def extract_role(text: str, nlp=None) -> str:
    # 1. Explicit label
    m = _ROLE_LABEL_RE.search(text)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) < 80:
            return candidate

    # 2. Keyword pattern in first 600 chars (title usually appears early)
    m = _TITLE_RE.search(text[:600])
    if m:
        return m.group(0).strip().title()

    # 3. spaCy — look for a short sentence near the top that looks like a title
    if nlp:
        lines = [l.strip() for l in text[:800].splitlines() if l.strip()]
        for line in lines[:15]:
            if 3 < len(line) < 80 and _TITLE_RE.search(line):
                return line

    return ""


# ---------------------------------------------------------------------------
# Notes summary
# ---------------------------------------------------------------------------

_REQ_SECTION_RE = re.compile(
    r'(?:requirements?|qualifications?|what you.ll need|what we.re looking for|'
    r'minimum qualifications?|basic qualifications?)[:\s]*\n(.*?)(?:\n\n|\Z)',
    re.IGNORECASE | re.DOTALL,
)

_YEARS_EXP_RE = re.compile(
    r'(\d+\+?\s*(?:to\s*\d+\s*)?years?\s+(?:of\s+)?experience)',
    re.IGNORECASE,
)

def extract_notes(text: str) -> str:
    snippets = []

    # Years of experience
    exp = _YEARS_EXP_RE.search(text)
    if exp:
        snippets.append(exp.group(1).strip())

    # Pull first 2 bullet points from requirements section
    m = _REQ_SECTION_RE.search(text)
    if m:
        section = m.group(1)
        bullets = re.findall(r'[•\-\*]\s*(.+)', section)
        if not bullets:
            bullets = [l.strip() for l in section.splitlines() if l.strip()]
        bullets = [b.strip() for b in bullets if 10 < len(b.strip()) < 120][:2]
        snippets.extend(bullets)

    if snippets:
        return '. '.join(snippets[:3]).strip('. ') + '.'

    # Fallback: first substantive paragraph
    paras = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 80]
    if paras:
        return paras[0][:200].rsplit(' ', 1)[0] + '…'

    return ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_job_posting(text: str, url: str) -> dict:
    """Parse scraped job posting text into structured fields."""
    nlp = _get_nlp()

    return {
        "company":  extract_company(text, url, nlp),
        "role":     extract_role(text, nlp),
        "location": extract_location(text, nlp),
        "salary":   extract_salary(text),
        "notes":    extract_notes(text),
    }
