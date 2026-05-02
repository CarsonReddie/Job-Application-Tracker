#!/usr/bin/env python3
"""Job Application Tracker — local web app (Flask + JSON storage)"""

import csv
import hashlib
import io
import json
import os
import secrets
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, request, send_from_directory, Response, redirect

STATUSES = ["applied", "interview", "offer", "rejected", "ghosted", "withdrawn"]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
DATA_FILE = BASE_DIR / "applications.json"
STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SETTINGS_FILE = BASE_DIR / "settings.json"

DEFAULT_TEMPLATES = [
    {"id": "tpl_followup_applied", "name": "Follow-up after applying", "subject": "Following up on {{role}} application",
     "body": "Hi,\n\nI recently applied for the {{role}} position at {{company}} and wanted to follow up on my application. I remain very interested in the opportunity and would welcome the chance to discuss how my background aligns with your team's needs.\n\nThank you for your time and consideration.\n\nBest regards,\n{{your_name}}"},
    {"id": "tpl_followup_interview", "name": "Follow-up after interview", "subject": "Thank you — {{role}} interview",
     "body": "Hi,\n\nThank you for taking the time to speak with me about the {{role}} position at {{company}}. I enjoyed learning more about the team and the work you're doing.\n\nI'm even more excited about the opportunity and am confident that my skills would be a strong fit.\n\nPlease let me know if you need any additional information from me.\n\nBest regards,\n{{your_name}}"},
    {"id": "tpl_checkin", "name": "General check-in", "subject": "Checking in — {{role}} at {{company}}",
     "body": "Hi,\n\nI wanted to check in on the status of my application for the {{role}} position. I'm still very interested and would love to hear about next steps.\n\nThank you,\n{{your_name}}"},
    {"id": "tpl_thankyou", "name": "Thank you note", "subject": "Thank you — {{company}}",
     "body": "Hi,\n\nThank you for the opportunity to interview for the {{role}} position. I truly enjoyed our conversation and learning more about {{company}}.\n\nI'm very enthusiastic about the role and look forward to hearing from you.\n\nBest regards,\n{{your_name}}"},
    {"id": "tpl_decline_offer", "name": "Decline offer", "subject": "{{role}} position — {{your_name}}",
     "body": "Hi,\n\nThank you so much for offering me the {{role}} position at {{company}}. I sincerely appreciate the time and effort you and the team invested in the interview process.\n\nAfter careful consideration, I've decided to pursue another opportunity that aligns more closely with my current goals.\n\nI wish you and the team all the best.\n\nSincerely,\n{{your_name}}"},
]

def default_settings():
    return {
        "reminder_days": 14,
        "your_name": "",
        "email_templates": DEFAULT_TEMPLATES,
        "auth": {"enabled": False, "hash": "", "salt": ""},
        "session_key": secrets.token_hex(16),
    }

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt

def check_auth(username, password):
    settings = load_settings()
    auth = settings.get("auth", {})
    if not auth.get("enabled"):
        return True
    if auth.get("username") != username:
        return False
    expected, _ = hash_password(password, auth.get("salt", ""))
    return expected == auth.get("hash", "")

def require_auth(f):
    """Decorator that blocks API calls when auth is enabled and session is missing."""
    def wrapper(*args, **kwargs):
        settings = load_settings()
        auth = settings.get("auth", {})
        if not auth.get("enabled"):
            return f(*args, **kwargs)
        token = request.cookies.get("jt_session")
        if not token or token != auth.get("session_key"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return default_settings()

def save_settings(s):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_apps():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []

def save_apps(apps):
    with open(DATA_FILE, "w") as f:
        json.dump(apps, f, indent=2)

def record_history(app_entry, new_status):
    history = app_entry.get("history", [])
    history.append({
        "status": new_status,
        "at": datetime.now().isoformat(),
    })
    app_entry["history"] = history
    app_entry["last_activity_date"] = datetime.today().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_url(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript"]):
        tag.decompose()

    # Try to find the most relevant content block
    for selector in ["main", "article", '[class*="job"]', '[class*="posting"]',
                     '[class*="description"]', '[id*="job"]', '[id*="content"]']:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text[:8000]

    return soup.get_text(separator="\n", strip=True)[:8000]

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/api/auth", methods=["POST"])
def auth_login():
    data = request.json
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if check_auth(username, password):
        settings = load_settings()
        token = settings.get("auth", {}).get("session_key", secrets.token_hex(16))
        resp = jsonify({"ok": True})
        resp.set_cookie("jt_session", token, httponly=True, max_age=86400*30)
        return resp
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/auth", methods=["GET"])
def auth_status():
    settings = load_settings()
    auth = settings.get("auth", {})
    return jsonify({"enabled": auth.get("enabled", False)})

@app.route("/api/auth/setup", methods=["PUT"])
def auth_setup():
    data = request.json
    password = data.get("password") or ""
    username = (data.get("username") or "").strip()
    settings = load_settings()
    if not password:
        settings["auth"]["enabled"] = False
        settings["auth"].pop("hash", None)
        settings["auth"].pop("salt", None)
        settings["auth"]["session_key"] = secrets.token_hex(16)
    else:
        h, s = hash_password(password)
        settings["auth"].update({"enabled": True, "hash": h, "salt": s, "username": username or "admin"})
        settings["auth"]["session_key"] = secrets.token_hex(16)
    save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/apps", methods=["GET"])
def get_apps():
    return jsonify(load_apps())

@app.route("/api/apps", methods=["POST"])
@require_auth
def add_app():
    data = request.json
    apps = load_apps()
    now = datetime.now().isoformat()
    today_str = datetime.today().strftime("%Y-%m-%d")
    status = data.get("status", "applied")
    entry = {
        "id":       str(uuid.uuid4()),
        "company":  data.get("company", "").strip(),
        "role":     data.get("role", "").strip(),
        "status":   status,
        "date":     data.get("date", today_str),
        "location": data.get("location", "").strip(),
        "salary":   data.get("salary", "").strip(),
        "url":      data.get("url", "").strip(),
        "notes":    data.get("notes", "").strip(),
        "tags":     [t.strip().lower() for t in (data.get("tags") or []) if t.strip()],
        "created":  now,
        "last_activity_date": today_str,
        "history": [{"status": status, "at": now}],
    }
    apps.insert(0, entry)
    save_apps(apps)
    return jsonify(entry), 201

@app.route("/api/apps/<app_id>", methods=["PUT"])
@require_auth
def update_app(app_id):
    data = request.json
    apps = load_apps()
    for i, a in enumerate(apps):
        if a["id"] == app_id:
            old_status = a.get("status")
            new_status = data.get("status", old_status)
            apps[i].update({
                "company":  data.get("company", a["company"]).strip(),
                "role":     data.get("role", a["role"]).strip(),
                "status":   new_status,
                "date":     data.get("date", a["date"]),
                "location": data.get("location", a.get("location", "")).strip(),
                "salary":   data.get("salary", a.get("salary", "")).strip(),
                "url":      data.get("url", a.get("url", "")).strip(),
                "notes":    data.get("notes", a.get("notes", "")).strip(),
                "tags":     [t.strip().lower() for t in (data.get("tags") or a.get("tags", [])) if t.strip()],
                "updated":  datetime.now().isoformat(),
            })
            if new_status != old_status:
                record_history(apps[i], new_status)
            save_apps(apps)
            return jsonify(apps[i])
    return jsonify({"error": "Not found"}), 404

@app.route("/api/apps/<app_id>", methods=["DELETE"])
@require_auth
def delete_app(app_id):
    apps = load_apps()
    apps = [a for a in apps if a["id"] != app_id]
    save_apps(apps)
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@app.route("/api/tags", methods=["GET"])
def get_tags():
    apps = load_apps()
    tag_counts = {}
    for a in apps:
        for t in a.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    return jsonify({"tags": sorted(tag_counts.items(), key=lambda x: -x[1])})

@app.route("/api/apps/<app_id>/tags", methods=["POST"])
@require_auth
def add_tag(app_id):
    data = request.json
    tag = (data.get("tag") or "").strip().lower()
    if not tag:
        return jsonify({"error": "Empty tag"}), 400
    apps = load_apps()
    for a in apps:
        if a["id"] == app_id:
            if "tags" not in a:
                a["tags"] = []
            if tag not in a["tags"]:
                a["tags"].append(tag)
            save_apps(apps)
            return jsonify({"ok": True, "tags": a["tags"]})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/apps/<app_id>/tags/<tag>", methods=["DELETE"])
@require_auth
def remove_tag(app_id, tag):
    apps = load_apps()
    for a in apps:
        if a["id"] == app_id:
            a["tags"] = [t for t in a.get("tags", []) if t != tag]
            save_apps(apps)
            return jsonify({"ok": True, "tags": a["tags"]})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/scrape", methods=["POST"])
@require_auth
def scrape():
    data = request.json
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        text = scrape_url(url)
    except Exception as e:
        return jsonify({"error": f"Could not fetch URL: {e}"}), 400

    try:
        from parser import parse_job_posting
        parsed = parse_job_posting(text, url)
    except Exception as e:
        return jsonify({"error": f"Parsing failed: {e}"}), 500

    # Report whether spaCy NER was available
    try:
        import spacy
        spacy.load("en_core_web_sm")
        parsed["_ner"] = True
    except Exception:
        parsed["_ner"] = False

    return jsonify(parsed)

@app.route("/api/status", methods=["GET"])
def status():
    """Report which optional features are available."""
    ner = False
    try:
        import spacy
        spacy.load("en_core_web_sm")
        ner = True
    except Exception:
        pass
    return jsonify({"spacy_ner": ner})

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(load_settings())

@app.route("/api/settings", methods=["PUT"])
@require_auth
def put_settings():
    s = load_settings()
    s.update(request.json)
    save_settings(s)
    return jsonify(s)

@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    """Return applications that have been idle beyond the threshold."""
    settings = load_settings()
    threshold = settings.get("reminder_days", 14)
    apps = load_apps()
    stale = []
    cutoff = datetime.today()
    for a in apps:
        if a.get("status") not in ("applied", "interview"):
            continue
        last = a.get("last_activity_date") or a.get("date")
        if not last:
            continue
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d")
        except ValueError:
            continue
        if (cutoff - last_dt).days >= threshold:
            stale.append({
                "id": a["id"],
                "company": a["company"],
                "role": a["role"],
                "status": a["status"],
                "last_activity_date": last,
                "days_idle": (cutoff - last_dt).days,
            })
    return jsonify({"threshold": threshold, "stale": stale})

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    apps = load_apps()
    now = datetime.now()
    total = len(apps)
    counts = {s: 0 for s in STATUSES}
    for a in apps:
        st = a.get("status", "")
        if st in counts:
            counts[st] += 1

    applied = counts.get("applied", 0)
    interviewed = counts.get("interview", 0)
    offers = counts.get("offer", 0)

    response_rate = round(interviewed / applied * 100, 1) if applied > 0 else 0
    offer_rate = round(offers / total * 100, 1) if total > 0 else 0

    # Stage transition times from history
    stage_durations = []
    for a in apps:
        hist = a.get("history", [])
        if len(hist) < 2:
            continue
        for i in range(1, len(hist)):
            try:
                t0 = datetime.fromisoformat(hist[i - 1]["at"])
                t1 = datetime.fromisoformat(hist[i]["at"])
                days = (t1 - t0).days
                if days >= 0:
                    stage_durations.append({"from": hist[i - 1]["status"], "to": hist[i]["status"], "days": days})
            except Exception:
                pass

    avg_stage = {}
    for sd in stage_durations:
        key = f"{sd['from']}→{sd['to']}"
        if key not in avg_stage:
            avg_stage[key] = []
        avg_stage[key].append(sd["days"])
    avg_stage = {k: round(sum(v) / len(v), 1) for k, v in avg_stage.items()}

    # Weekly trend (last 12 weeks)
    weekly = {}
    for a in apps:
        try:
            created = datetime.fromisoformat(a.get("created", ""))
            week = created.strftime("%Y-W%W")
            weekly[week] = weekly.get(week, 0) + 1
        except Exception:
            pass

    last_12 = []
    for i in range(11, -1, -1):
        week_start = now - timedelta(weeks=i)
        wk = week_start.strftime("%Y-W%W")
        label = f"Week {week_start.isocalendar()[1]}"
        last_12.append({"label": label, "count": weekly.get(wk, 0)})

    # Source breakdown if available
    source_counts = {}
    for a in apps:
        src = a.get("source", "Other")
        source_counts[src] = source_counts.get(src, 0) + 1

    # Current days in stage for active apps
    active_staleness = []
    for a in apps:
        if a.get("status") in ("applied", "interview"):
            last = a.get("last_activity_date") or a.get("date")
            if last:
                try:
                    days = (now - datetime.strptime(last, "%Y-%m-%d")).days
                    active_staleness.append(days)
                except ValueError:
                    pass
    avg_idle = round(sum(active_staleness) / len(active_staleness), 1) if active_staleness else 0

    # Tag performance
    tag_counts = {}
    tag_interview_counts = {}
    tag_offer_counts = {}
    for a in apps:
        for t in a.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
            if a.get("status") == "interview":
                tag_interview_counts[t] = tag_interview_counts.get(t, 0) + 1
            if a.get("status") == "offer":
                tag_offer_counts[t] = tag_offer_counts.get(t, 0) + 1
    tag_performance = []
    for t, cnt in tag_counts.items():
        tag_performance.append({
            "tag": t,
            "count": cnt,
            "interview_rate": round(tag_interview_counts.get(t, 0) / cnt * 100, 1) if cnt > 0 else 0,
            "offer_rate": round(tag_offer_counts.get(t, 0) / cnt * 100, 1) if cnt > 0 else 0,
        })
    tag_performance.sort(key=lambda x: -x["count"])

    return jsonify({
        "total": total,
        "counts": counts,
        "response_rate": response_rate,
        "offer_rate": offer_rate,
        "avg_stage_days": avg_stage,
        "weekly_trend": last_12,
        "avg_active_idle_days": avg_idle,
        "source_breakdown": source_counts,
        "tag_performance": tag_performance,
    })

# ---------------------------------------------------------------------------
# Email Templates
# ---------------------------------------------------------------------------

@app.route("/api/templates", methods=["GET"])
def get_templates():
    settings = load_settings()
    return jsonify({
        "your_name": settings.get("your_name", ""),
        "templates": settings.get("email_templates", DEFAULT_TEMPLATES),
    })

@app.route("/api/templates", methods=["PUT"])
@require_auth
def put_template():
    data = request.json
    if "template" not in data:
        return jsonify({"error": "No template provided"}), 400

    tpl = data["template"]
    settings = load_settings()
    templates = settings.get("email_templates", DEFAULT_TEMPLATES)

    if "id" in tpl and any(t.get("id") == tpl["id"] for t in templates):
        templates = [t if t.get("id") != tpl["id"] else tpl for t in templates]
    else:
        tpl["id"] = f"tpl_{uuid.uuid4().hex[:8]}"
        templates.append(tpl)

    settings["email_templates"] = templates
    if "your_name" in data:
        settings["your_name"] = data["your_name"]
    save_settings(settings)
    return jsonify({"id": tpl["id"]})

@app.route("/api/templates/<tpl_id>", methods=["DELETE"])
@require_auth
def delete_template(tpl_id):
    settings = load_settings()
    templates = settings.get("email_templates", [])
    templates = [t for t in templates if t.get("id") != tpl_id]
    settings["email_templates"] = templates
    save_settings(settings)
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# CSV Export / Import
# ---------------------------------------------------------------------------
CSV_FIELDS = ["company", "role", "status", "date", "location", "salary", "url", "notes", "created"]

@app.route("/api/export/csv", methods=["GET"])
@require_auth
def export_csv():
    apps = load_apps()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for a in apps:
        writer.writerow({f: a.get(f, "") for f in CSV_FIELDS})
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=jobtracker_{datetime.today().strftime('%Y%m%d')}.csv"})

@app.route("/api/import/csv", methods=["POST"])
@require_auth
def import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"error": "Must be a .csv file"}), 400

    apps = load_apps()
    now = datetime.now().isoformat()
    today_str = datetime.today().strftime("%Y-%m-%d")
    imported = 0
    skipped = 0

    for row in csv.DictReader(f):
        company = (row.get("company") or "").strip()
        role = (row.get("role") or "").strip()
        if not company and not role:
            skipped += 1
            continue
        entry = {
            "id": str(uuid.uuid4()),
            "company": company,
            "role": role,
            "status": (row.get("status") or "applied").strip(),
            "date": (row.get("date") or today_str).strip(),
            "location": (row.get("location") or "").strip(),
            "salary": (row.get("salary") or "").strip(),
            "url": (row.get("url") or "").strip(),
            "notes": (row.get("notes") or "").strip(),
            "created": now,
            "last_activity_date": today_str,
            "history": [{"status": row.get("status", "applied").strip(), "at": now}],
        }
        apps.insert(0, entry)
        imported += 1

    save_apps(apps)
    return jsonify({"imported": imported, "skipped": skipped})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def open_browser(port):
    webbrowser.open(f"http://127.0.0.1:{port}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5757))
    print(f"\n  Job Tracker running at http://127.0.0.1:{port}")

    # Report parser status
    try:
        import spacy
        spacy.load("en_core_web_sm")
        print("  Parser: spaCy NER + regex (full)")
    except Exception:
        print("  Parser: regex only (install spaCy + en_core_web_sm for better results)")

    print("  Press Ctrl+C to stop.\n")
    Timer(1.0, open_browser, args=[port]).start()
    app.run(host="127.0.0.1", port=port, debug=False)
