#!/usr/bin/env python3
"""CRISIS Intelligence candidate news collection.

Two discovery channels: Google News RSS (experimental, undocumented public feed)
and GDELT DOC 2.0. No article is a verified event and no threat score is computed.
Only article metadata and outbound links are stored.
"""
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "site" / "data"
ROOT.mkdir(parents=True, exist_ok=True)
UA = "CRISIS-Intelligence-Research-Pilot/0.3 (public-source-monitor)"
MAX_AGE_DAYS = 45

# Eight topical profiles and four extra non-Western/regional source perspectives.
# Regional searches are labels for discovery, NOT evidence of article origin.
PROFILES = [
    ("military", "Militair & veiligheid", "Iran Hormuz military missile attacks when:2d", "en-US", "US", "US:en"),
    ("diplomacy", "Politiek & diplomatie", "Iran diplomacy ceasefire talks negotiations when:2d", "en-US", "US", "US:en"),
    ("government", "Overheden & crisismaatregelen", "Iran Saudi evacuation embassy travel warning when:2d", "en-US", "US", "US:en"),
    ("markets", "Financiële markten", "Iran Hormuz oil futures insurance bonds when:2d", "en-US", "US", "US:en"),
    ("energy", "Energie & grondstoffen", "Hormuz crude oil diesel LNG refinery when:2d", "en-US", "US", "US:en"),
    ("trade", "Wereldhandel & logistiek", "Hormuz tanker shipping airline disruption when:2d", "en-US", "US", "US:en"),
    ("business", "Bedrijfsleven & investeringen", "Middle East company staff evacuation airlines when:2d", "en-US", "US", "US:en"),
    ("economy", "Economie & samenleving", "Iran war inflation shortages tourism economy when:2d", "en-US", "US", "US:en"),
    ("iran-fa", "Regionaal: Iran / Perzisch", "ایران تنگه هرمز اقتصاد جنگ when:2d", "fa", "IR", "IR:fa"),
    ("china-zh", "Regionaal: China / Chinees", "伊朗 霍尔木兹 石油 中国 when:2d", "zh-CN", "CN", "CN:zh-Hans"),
    ("pakistan-en", "Regionaal: Pakistan", "Pakistan Iran Saudi diplomacy oil when:2d", "en-PK", "PK", "PK:en"),
    ("gulf-ar", "Regionaal: Golfstaten / Arabisch", "إيران مضيق هرمز السعودية النفط when:2d", "ar", "SA", "SA:ar"),
]
GDELT_QUERIES = [
    ("gdelt-iran", "Iran"),
    ("gdelt-hormuz", '"Strait of Hormuz"'),
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value):
    if not isinstance(value, dt.datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_gdelt_date(value):
    value = str(value or "")
    if re.fullmatch(r"\d{8}T\d{6}Z?", value):
        try:
            return iso(dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S"))
        except ValueError:
            pass
    return ""


def parse_pubdate(value):
    try:
        return iso(email.utils.parsedate_to_datetime(value))
    except (TypeError, ValueError, IndexError):
        return ""


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def http_get(url, attempts=2):
    error = ""
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/rss+xml, application/xml, application/json, */*",
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read(4_000_000), None
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code} {exc.reason}"
            if exc.code == 429 and attempt < attempts - 1:
                retry = exc.headers.get("Retry-After", "")
                try:
                    pause = min(60, max(10, int(retry)))
                except (ValueError, TypeError):
                    pause = 12 * (attempt + 1)
                time.sleep(pause)
            elif attempt < attempts - 1:
                time.sleep(5)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:130]}"
            if attempt < attempts - 1:
                time.sleep(5)
    return None, error


def rss_url(query, lang, region, edition):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": lang, "gl": region, "ceid": edition,
    })


def parse_rss(raw, profile, captured_at):
    root = ET.fromstring(raw)
    if root.tag != "rss":
        raise ValueError("Expected RSS XML")
    rows = []
    for item in root.findall("./channel/item"):
        def txt(name):
            node = item.find(name)
            return (node.text or "").strip() if node is not None else ""
        url = txt("link")
        if not url.startswith(("https://", "http://")):
            continue
        source = item.find("source")
        publisher = (source.text or "").strip() if source is not None else ""
        publisher_url = (source.get("url", "") if source is not None else "")
        stable_id = txt("guid") or url
        title = html.unescape(re.sub(r"\s+", " ", txt("title")))[:350]
        if not title:
            continue
        key = hashlib.sha256(("google-rss:" + stable_id).encode("utf-8")).hexdigest()[:24]
        rows.append({
            "key": key,
            "url": url,
            "title": title,
            "publisher": publisher,
            "publisher_url": publisher_url,
            "domain": urllib.parse.urlparse(publisher_url).hostname or "news.google.com",
            "first_seen": captured_at,
            "published_at": parse_pubdate(txt("pubDate")),
            "language": profile[3],
            "sourcecountry": "",  # Feed locale is NOT the publishing country.
            "discovery_profiles": [profile[0]],
            "topic": [profile[1]],
            "provider": "google_news_rss",
            "review_status": "unverified",
        })
    return rows


def parse_gdelt(raw, profile_name, captured_at):
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise ValueError("Missing GDELT articles list")
    rows = []
    for item in payload["articles"]:
        url = str(item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        title = html.unescape(str(item.get("title") or "")).strip()[:350]
        if not title:
            continue
        rows.append({
            "key": hashlib.sha256(("gdelt:" + url).encode("utf-8")).hexdigest()[:24],
            "url": url,
            "title": title,
            "publisher": item.get("domain") or "",
            "publisher_url": "",
            "domain": item.get("domain") or urllib.parse.urlparse(url).hostname or "",
            "first_seen": captured_at,
            "published_at": parse_gdelt_date(item.get("seendate")),
            "language": item.get("language") or "",
            "sourcecountry": item.get("sourcecountry") or "",
            "discovery_profiles": [profile_name],
            "topic": ["Brede GDELT-detectie"],
            "provider": "gdelt_doc2",
            "review_status": "unverified",
        })
    return rows


def merge_articles(existing, incoming):
    # Exact-link dedup within the provider. Cross-provider event clustering
    # is a future, separate verification step.
    keys = {}
    for obj in existing:
        if not isinstance(obj, dict) or not obj.get("url"):
            continue
        key = str(obj.get("key") or hashlib.sha256(
            (str(obj.get("provider") or "legacy") + ":" + obj["url"]).encode("utf-8")
        ).hexdigest()[:24])
        obj["key"] = key
        keys[key] = obj
    added = 0
    for obj in incoming:
        key = obj["key"]
        if key not in keys:
            keys[key] = obj
            added += 1
        else:
            old = keys[key]
            for field in ("topic", "discovery_profiles"):
                old[field] = sorted(set(old.get(field, []) + obj.get(field, [])))
            if not old.get("published_at") and obj.get("published_at"):
                old["published_at"] = obj["published_at"]
    return list(keys.values()), added


def keep_recent(obj, cutoff):
    stamp = obj.get("published_at") or obj.get("first_seen") or ""
    try:
        return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= cutoff
    except (TypeError, ValueError):
        return False


def main():
    now = utc_now()
    stamp = iso(now)
    old = read_json(ROOT / "articles.json", {"articles": []})
    results = list(old.get("articles", []))
    status = {"last_attempt_utc": stamp, "sources": {}, "profiles": {},
              "errors": {}, "new_urls": 0, "retained_urls": 0}
    good_sources = set()

    for profile in PROFILES:
        pid = profile[0]
        raw, error = http_get(rss_url(profile[2], profile[3], profile[4], profile[5]), attempts=2)
        if error:
            status["profiles"][pid] = {"status": "error", "error": error, "articles": 0}
            status["errors"]["rss:" + pid] = error
        else:
            try:
                parsed = parse_rss(raw, profile, stamp)
                results, new_count = merge_articles(results, parsed)
                status["new_urls"] += new_count
                status["profiles"][pid] = {"status": "ok", "articles": len(parsed),
                                           "new": new_count}
                good_sources.add("google_news_rss")
            except (ET.ParseError, ValueError) as exc:
                status["profiles"][pid] = {"status": "error", "error": str(exc)[:150], "articles": 0}
                status["errors"]["rss:" + pid] = str(exc)[:150]
        time.sleep(2)

    for pid, query in GDELT_QUERIES:
        params = urllib.parse.urlencode({
            "query": query, "mode": "artlist", "format": "json",
            "sort": "datedesc", "maxrecords": 40, "timespan": "2d",
        })
        raw, error = http_get("https://api.gdeltproject.org/api/v2/doc/doc?" + params, attempts=1)
        if not error:
            try:
                parsed = parse_gdelt(raw, pid, stamp)
                results, new_count = merge_articles(results, parsed)
                status["new_urls"] += new_count
                status["profiles"][pid] = {"status": "ok", "articles": len(parsed),
                                           "new": new_count}
                good_sources.add("gdelt_doc2")
            except (json.JSONDecodeError, ValueError) as exc:
                error = str(exc)[:150]
        if error:
            status["profiles"][pid] = {"status": "error", "error": error, "articles": 0}
            status["errors"][pid] = error
        time.sleep(5)

    total = len(PROFILES) + len(GDELT_QUERIES)
    ok = sum(p["status"] == "ok" for p in status["profiles"].values())
    status["queries_ok"] = ok
    status["queries_total"] = total
    status["status"] = "ok" if ok == total else ("partial" if ok else "error")
    status["sources"]["google_news_rss"] = {
        "ok": sum(status["profiles"][p[0]]["status"] == "ok" for p in PROFILES),
        "total": len(PROFILES),
    }
    status["sources"]["gdelt_doc2"] = {
        "ok": sum(status["profiles"][p[0]]["status"] == "ok" for p in GDELT_QUERIES),
        "total": len(GDELT_QUERIES),
    }
    cutoff = now - dt.timedelta(days=MAX_AGE_DAYS)
    results = sorted((x for x in results if keep_recent(x, cutoff)),
                     key=lambda x: x.get("published_at") or x.get("first_seen") or "",
                     reverse=True)[:8000]
    status["retained_urls"] = len(results)
    if good_sources:
        (ROOT / "articles.json").write_text(json.dumps({
            "source": "Google News RSS (experimental) + GDELT DOC 2.0",
            "description": "Candidate headlines and links only; NOT verified events or risk scores",
            "last_success_utc": stamp,
            "articles": results,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "fetch_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {ok}/{total} feeds; {status['new_urls']} new candidate articles; "
          f"{len(results)} retained; {len(status['errors'])} errors")


if __name__ == "__main__":
    main()
