#!/usr/bin/env python3
"""Refresh public HealthScope source metadata; no patient data, no AI-generated claims."""
import email.utils
import hashlib
import html
import json
import os
import re
import smtplib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
UPDATES = DATA / "updates.json"
STATUS = DATA / "status.json"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
UA = "HealthScope-Educational-Metadata/1.0 (https://github.com/michaeljamesanalytics-art/healthscope)"
TOPICS = {
    "Digital health": ("digital health", "health information", "electronic health", "interoperab", "health data", "health informatics", "telehealth"),
    "AI in healthcare": ("artificial intelligence", "machine learning", "ai-assisted"),
    "Public health": ("vaccination", "immuniz", "outbreak", "surveillance", "epidemic", "malaria"),
    "Healthcare systems": ("health system", "hospital", "health workforce", "health financing"),
    "Clinical trials": ("clinical trial", "randomized", "trial registration"),
}
REGIONS = {
    "Africa": ("africa", "nigeria", "kenya", "rwanda", "south africa", "uganda", "ghana", "ethiopia"),
    "Europe": ("europe", "united kingdom", "germany", "france"),
    "Asia-Pacific": ("asia", "japan", "china", "india", "australia"),
    "Americas": ("brazil", "canada", "mexico", "united states", "latin america"),
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=22) as response:
        return response.read()

def textclean(value, size=440):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    value = re.sub(r"\s+", " ", html.unescape(value)).strip()
    return value[:size]

def dateclean(value):
    if not value:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", str(value)):
        return str(value)[:10]
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return ""

def metadata(title, url, source, kind, date, description):
    if not url.startswith("https://") or not title:
        return None
    low = title.lower()
    cat = next((category for category, words in TOPICS.items() if any(word in low for word in words)), "Research & evidence" if kind == "Research citation" else "Other")
    region = next((name for name, words in REGIONS.items() if any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)), "Global / unspecified")
    return {
        "id": hashlib.sha256(url.encode()).hexdigest()[:20], "title": textclean(title, 220),
        "url": url, "source": source, "source_type": kind,
        "published": dateclean(date), "category": cat, "region": region,
        "summary": textclean(description) or "Review the original source for details, context and limitations."
    }

def who_feed():
    data = ET.fromstring(fetch("https://www.who.int/rss-feeds/news-english.xml"))
    items = []
    for item in data.findall(".//item")[:35]:
        url = (item.findtext("link") or "").strip().replace("http://www.who.int/", "https://www.who.int/")
        entry = metadata(item.findtext("title", ""), url, "World Health Organization", "Official announcement",
                         item.findtext("pubDate", ""), item.findtext("description", ""))
        if entry:
            items.append(entry)
    return items

def pubmed_feed():
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    term = '("digital health"[Title/Abstract] OR "health informatics"[Title/Abstract] OR "health data quality"[Title/Abstract]) AND ("last 14 days"[PDat])'
    query = urllib.parse.urlencode({"db": "pubmed", "term": term, "retmax": 18, "retmode": "json", "sort": "pub date", "tool": "HealthScope"})
    results = json.loads(fetch(base + "esearch.fcgi?" + query)).get("esearchresult", {})
    ids = results.get("idlist", [])
    if not ids:
        return []
    summary_query = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": "HealthScope"})
    records = json.loads(fetch(base + "esummary.fcgi?" + summary_query)).get("result", {})
    items = []
    for ident in ids:
        r = records.get(ident, {})
        entry = metadata(r.get("title"), "https://pubmed.ncbi.nlm.nih.gov/" + ident + "/", "PubMed · " + textclean(r.get("source", ""), 65),
                         "Research citation", r.get("sortpubdate") or r.get("pubdate"),
                         "Indexed research citation. Verify study design, sample, results and limitations in the original publication.")
        if entry:
            items.append(entry)
    return items

def clinical_trials():
    params = urllib.parse.urlencode({"query.term": "digital health OR telehealth", "pageSize": 18, "format": "json", "sort": "LastUpdatePostDate:desc"})
    records = json.loads(fetch("https://clinicaltrials.gov/api/v2/studies?" + params)).get("studies", [])
    items = []
    for r in records:
        p = r.get("protocolSection", {})
        ident = p.get("identificationModule", {})
        status = p.get("statusModule", {})
        nct = ident.get("nctId", "")
        if not nct:
            continue
        updated = status.get("lastUpdatePostDateStruct", {}).get("date") or status.get("studyFirstPostDateStruct", {}).get("date")
        entry = metadata(ident.get("briefTitle"), "https://clinicaltrials.gov/study/" + nct,
                         "ClinicalTrials.gov", "Clinical trial registry", updated,
                         "Registered study (status: " + status.get("overallStatus", "unspecified") + "). Registration is not proof of effectiveness.")
        if entry:
            entry["category"] = "Clinical trials"
            items.append(entry)
    return items

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default

def email_digest(new):
    required = {k: os.environ.get(k, "").strip() for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "DIGEST_TO_EMAIL")}
    if not all(required.values()):
        print("Daily email disabled; SMTP secrets not configured.")
        return
    lines = ["HealthScope · Daily Healthcare Source Briefing", NOW[:10],
             "", "Read sources directly. Official announcements, trial registrations and research citations are different evidence types.", ""]
    for r in new[:8]:
        lines += [r["title"], r["source"] + " | " + r.get("published", ""), r["url"], ""]
    if not new:
        lines.append("No new source records were found today.")
    msg = EmailMessage()
    msg["Subject"] = "HealthScope source briefing | " + NOW[:10]
    msg["From"] = os.environ.get("SMTP_FROM_EMAIL") or required["SMTP_USER"]
    msg["To"] = required["DIGEST_TO_EMAIL"]
    msg.set_content("\n".join(lines))
    with smtplib.SMTP(required["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")), timeout=20) as smtp:
        smtp.starttls()
        smtp.login(required["SMTP_USER"], required["SMTP_PASSWORD"])
        smtp.send_message(msg)
    print("Optional email briefing sent.")

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    old = load(UPDATES, [])
    old_urls = {r.get("url") for r in old}
    combined = {r["url"]: r for r in old if r.get("url")}
    states, collected, ok = {}, [], 0
    for name, fn in (("WHO", who_feed), ("PubMed", pubmed_feed), ("ClinicalTrials.gov", clinical_trials)):
        try:
            records = fn()
            collected.extend(records)
            states[name] = {"status": "ok", "count": len(records)}
            ok += 1
        except Exception as exc:
            states[name] = {"status": "error", "detail": str(exc)[:130]}
    if ok:
        for r in collected:
            combined[r["url"]] = r
        recent = sorted(combined.values(), key=lambda r: r.get("published", ""), reverse=True)[:150]
        UPDATES.write_text(json.dumps(recent, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    status = {"mode": "Automated source metadata", "last_attempted_refresh": NOW,
              "last_successful_refresh": NOW if ok else load(STATUS, {}).get("last_successful_refresh"),
              "sources": states, "note": "Source availability and scheduled run times are not guaranteed."}
    STATUS.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    if ok:
        added = [r for r in collected if r.get("url") not in old_urls]
        try:
            email_digest(sorted(added, key=lambda r: r.get("published", ""), reverse=True))
        except Exception as exc:
            print("Optional email delivery failed: " + str(exc)[:130])
    print(json.dumps(status))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
