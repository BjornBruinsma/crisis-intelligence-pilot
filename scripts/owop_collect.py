#!/usr/bin/env python3
"""Collect public candidate stories for One World. One People.

Discovery only. No article is automatically treated as true or positive merely
because a query matched it. Stores metadata/links, not full copyrighted text.
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

ROOT = Path(__file__).resolve().parents[1] / "site" / "owop" / "data"
ROOT.mkdir(parents=True, exist_ok=True)
UA = "OWOP-News-Pilot/0.1 (public-source-monitor)"
MAX_AGE_DAYS = 14

# Broad OR searches are intentional: AI performs the strict editorial filtering later.
PROFILES = [
    ("nature-en", "Nature", "(conservation OR restored OR recovery OR rescued OR biodiversity) when:2d", "en-US", "US", "US:en"),
    ("health-en", "Health", "(breakthrough OR recovered OR treatment OR survival OR cured) health when:2d", "en-US", "US", "US:en"),
    ("science-en", "Science", "(breakthrough OR discovery OR innovation OR solution) science when:2d", "en-US", "US", "US:en"),
    ("people-en", "People", "(volunteers OR community OR rescued OR rebuilt OR helped) when:2d", "en-US", "US", "US:en"),
    ("progress-en", "Progress", "(declined OR improved OR reduced OR expanded OR record) (poverty OR mortality OR education OR access) when:2d", "en-US", "US", "US:en"),
    ("energy-en", "Climate & Energy", "(renewable OR battery OR solar OR wind OR clean energy) (record OR breakthrough OR expansion) when:2d", "en-US", "US", "US:en"),
    ("spanish", "Mundo hispano", "(restauración OR conservación OR voluntarios OR recuperación OR avance OR rescate) when:2d", "es", "ES", "ES:es"),
    ("portuguese", "Mundo lusófono", "(restauração OR conservação OR voluntários OR recuperação OR avanço OR resgate) when:2d", "pt-BR", "BR", "BR:pt-419"),
    ("french", "Monde francophone", "(restauration OR conservation OR bénévoles OR rétablissement OR progrès OR sauvetage) when:2d", "fr", "FR", "FR:fr"),
    ("indonesia", "Indonesia", "(konservasi OR pemulihan OR relawan OR kemajuan OR penyelamatan OR berhasil) when:2d", "id", "ID", "ID:id"),
    ("russian", "Русскоязычные источники", "(восстановили OR волонтеры OR спасли OR улучшение OR восстановление OR экология) when:2d", "ru", "RU", "RU:ru"),
    ("arabic", "مصادر عربية", "(إنقاذ OR استعادة OR تحسن OR تطوع OR مبادرة OR حماية) when:2d", "ar", "SA", "SA:ar"),
    ("china", "中文来源", "(保护 OR 恢复 OR 志愿者 OR 改善 OR 突破 OR 救援) when:2d", "zh-CN", "CN", "CN:zh-Hans"),
]

# GDELT's public DOC endpoint is rate-limited in Actions; use one broad radar call.
GDELT_QUERIES = [
    ("gdelt-positive-radar", '(conservation OR restored OR recovery OR rescued OR breakthrough OR volunteers OR improved) tone>1'),
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value):
    if not isinstance(value, dt.datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_pubdate(value):
    try:
        return iso(email.utils.parsedate_to_datetime(value))
    except (TypeError, ValueError, IndexError):
        return ""


def parse_gdelt_date(value):
    value = str(value or "")
    if re.fullmatch(r"\d{8}T\d{6}Z?", value):
        try:
            return iso(dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S"))
        except ValueError:
            pass
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
            if attempt < attempts - 1:
                time.sleep(10 if exc.code == 429 else 4)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:140]}"
            if attempt < attempts - 1:
                time.sleep(4)
    return None, error


def rss_url(query, lang, region, edition):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": lang, "gl": region, "ceid": edition,
    })


def parse_rss(raw, profile, captured_at):
    root = ET.fromstring(raw)
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
        publisher_url = source.get("url", "") if source is not None else ""
        stable_id = txt("guid") or url
        title = html.unescape(re.sub(r"\s+", " ", txt("title")))[:350]
        if not title:
            continue
        rows.append({
            "key": hashlib.sha256(("google-rss:" + stable_id).encode()).hexdigest()[:24],
            "url": url,
            "title": title,
            "publisher": publisher,
            "publisher_url": publisher_url,
            "domain": urllib.parse.urlparse(publisher_url).hostname or "news.google.com",
            "first_seen": captured_at,
            "published_at": parse_pubdate(txt("pubDate")),
            "language": profile[3],
            "sourcecountry": "",
            "discovery_profiles": [profile[0]],
            "topic": [profile[1]],
            "provider": "google_news_rss",
        })
    return rows


def parse_gdelt(raw, profile_name, captured_at):
    payload = json.loads(raw)
    rows = []
    for item in payload.get("articles", []):
        url = str(item.get("url") or "").strip()
        title = html.unescape(str(item.get("title") or "").strip())[:350]
        if not url.startswith(("https://", "http://")) or not title:
            continue
        rows.append({
            "key": hashlib.sha256(("gdelt:" + url).encode()).hexdigest()[:24],
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
            "topic": ["GDELT discovery"],
            "provider": "gdelt_doc2",
        })
    return rows


def merge_articles(existing, incoming):
    rows = {str(x.get("key")): x for x in existing if isinstance(x, dict) and x.get("key")}
    added = 0
    for obj in incoming:
        key = obj["key"]
        if key not in rows:
            rows[key] = obj
            added += 1
        else:
            old = rows[key]
            for field in ("topic", "discovery_profiles"):
                old[field] = sorted(set(old.get(field, []) + obj.get(field, [])))
    return list(rows.values()), added


def keep_recent(obj, cutoff):
    stamp = obj.get("published_at") or obj.get("first_seen") or ""
    try:
        return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= cutoff
    except (TypeError, ValueError):
        return False


def main():
    now = utc_now()
    stamp = iso(now)
    store = read_json(ROOT / "articles.json", {"articles": []})
    results = list(store.get("articles") or [])
    status = {"last_attempt_utc": stamp, "profiles": {}, "errors": {}, "new_urls": 0}

    for profile in PROFILES:
        raw, error = http_get(rss_url(profile[2], profile[3], profile[4], profile[5]))
        if error:
            status["profiles"][profile[0]] = {"status": "error", "error": error}
            status["errors"]["rss:" + profile[0]] = error
        else:
            try:
                parsed = parse_rss(raw, profile, stamp)
                results, new_count = merge_articles(results, parsed)
                status["new_urls"] += new_count
                status["profiles"][profile[0]] = {"status": "ok", "articles": len(parsed), "new": new_count}
            except Exception as exc:
                status["errors"]["rss:" + profile[0]] = str(exc)[:160]
        time.sleep(1)

    for pid, query in GDELT_QUERIES:
        params = urllib.parse.urlencode({
            "query": query, "mode": "artlist", "format": "json",
            "sort": "datedesc", "maxrecords": 60, "timespan": "2d",
        })
        raw, error = http_get("https://api.gdeltproject.org/api/v2/doc/doc?" + params, attempts=1)
        if error:
            status["errors"][pid] = error
            continue
        try:
            parsed = parse_gdelt(raw, pid, stamp)
            results, new_count = merge_articles(results, parsed)
            status["new_urls"] += new_count
            status["profiles"][pid] = {"status": "ok", "articles": len(parsed), "new": new_count}
        except Exception as exc:
            status["errors"][pid] = str(exc)[:160]
        time.sleep(1)

    cutoff = now - dt.timedelta(days=MAX_AGE_DAYS)
    results = [x for x in results if keep_recent(x, cutoff)]
    results.sort(key=lambda x: x.get("published_at") or x.get("first_seen") or "", reverse=True)
    payload = {"last_success_utc": stamp, "article_count": len(results), "articles": results}
    (ROOT / "articles.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status["retained_urls"] = len(results)
    (ROOT / "fetch_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OWOP collected {len(results)} retained articles; {status['new_urls']} new")


if __name__ == "__main__":
    main()
