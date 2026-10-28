#!/usr/bin/env python3
"""OWOP source verification desk.

Takes the strongest editorial candidates, attempts to retrieve their linked source
pages, extracts readable text snippets, and asks a separate AI verifier whether
the claimed positive outcome is actually supported.

This is a pilot verification layer, not a guarantee of truth. It deliberately
records inaccessible sources and uncertainty instead of treating missing evidence
as confirmation.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "site" / "owop"
DATA = ROOT / "data"
EDITORIAL = DATA / "editorial.json"
OUTPUT = DATA / "verification.json"
MODEL = os.getenv("OWOP_VERIFY_MODEL", "gpt-4o-mini")
MAX_STORIES = 16
MAX_SOURCES_PER_STORY = 3
MAX_HTML_BYTES = 900_000
MAX_TEXT_CHARS = 7000
UA = "Mozilla/5.0 (compatible; OWOP-Verification-Pilot/0.1)"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            value = re.sub(r"\s+", " ", data).strip()
            if len(value) >= 25:
                self.parts.append(value)


def clean_text(raw):
    parser = TextExtractor()
    try:
        parser.feed(raw)
    except Exception:
        pass
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT_CHARS]


def candidate_external_urls(raw_html):
    found = []
    for raw in re.findall(r'https?://[^"\'<>\\ ]+', raw_html):
        url = html.unescape(raw).replace("\\u0026", "&")
        try:
            p = urllib.parse.urlsplit(url)
        except ValueError:
            continue
        host = (p.hostname or "").casefold()
        if not host or host.endswith("google.com") or "gstatic.com" in host or "googleusercontent.com" in host:
            continue
        if url not in found:
            found.append(url)
    return found


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        final_url = resp.geturl()
        ctype = str(resp.headers.get("Content-Type") or "")
        body = resp.read(MAX_HTML_BYTES)
    if "html" not in ctype.casefold() and not body.lstrip().startswith(b"<"):
        return final_url, "", "non_html"
    decoded = body.decode("utf-8", errors="replace")
    return final_url, decoded, None


def retrieve_source(source):
    start_url = str(source.get("url") or "")
    result = {
        "publisher": source.get("publisher") or "Source",
        "title": source.get("title") or "",
        "start_url": start_url,
        "final_url": "",
        "status": "unavailable",
        "text": "",
        "error": "",
    }
    if not start_url.startswith(("http://", "https://")):
        result["error"] = "invalid_url"
        return result
    try:
        final_url, raw, error = fetch(start_url)
        result["final_url"] = final_url
        if error:
            result["error"] = error
            return result

        host = (urllib.parse.urlsplit(final_url).hostname or "").casefold()
        # Google News RSS often lands on an intermediate page. Try external links
        # embedded in that page before falling back to its visible text.
        if host.endswith("news.google.com"):
            for candidate in candidate_external_urls(raw)[:12]:
                try:
                    resolved, external_raw, external_error = fetch(candidate)
                    if not external_error:
                        text = clean_text(external_raw)
                        if len(text) >= 250:
                            result["final_url"] = resolved
                            result["status"] = "retrieved"
                            result["text"] = text
                            return result
                except Exception:
                    continue

        text = clean_text(raw)
        if len(text) >= 250:
            result["status"] = "retrieved"
            result["text"] = text
        else:
            result["error"] = "insufficient_readable_text"
        return result
    except urllib.error.HTTPError as exc:
        result["error"] = f"http_{exc.code}"
    except urllib.error.URLError as exc:
        result["error"] = "url_error:" + str(exc.reason)[:80]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{str(exc)[:100]}"
    return result


def parse_json_text(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    return json.loads(text)


def verify_with_ai(client, story, sources):
    evidence = []
    for s in sources:
        evidence.append({
            "publisher": s["publisher"],
            "source_title": s["title"],
            "retrieval_status": s["status"],
            "final_url": s["final_url"],
            "text_excerpt": s["text"],
            "error": s["error"],
        })

    system = """You are the verification editor for ONE WORLD. ONE PEOPLE. (OWOP).
You receive a proposed positive-news story plus text retrieved from linked sources.

Your job is NOT to reward optimism. Determine whether the source evidence actually
supports the concrete positive claim. Distinguish completed outcomes from launches,
plans, announcements, awards, PR and aspirational language. Do not infer facts that
are absent from the retrieved text. Multiple articles can repeat the same press
release, so source count is not automatically independence.

Return ONLY valid JSON:
{
  "support":"supported|partially_supported|unsupported|unavailable",
  "outcome_status":"completed|measured_progress|announcement|unclear",
  "evidence_quality":"high|medium|low",
  "independence":"multiple_independent|likely_republication|single_source|unclear",
  "verified_headline":"neutral English headline, max 14 words",
  "verified_summary":"1-2 sentences containing only supported facts",
  "verification_note":"max 40 words",
  "publish_recommendation":"publish|reserve|reject"
}

Use 'unavailable' if insufficient source text was retrieved. A mere launch or funding
announcement should normally be reserve/reject. A routine anecdote can be factually
supported yet still be reserve because it lacks OWOP significance."""

    payload = {"story": {
        "id": story.get("id"),
        "headline": story.get("headline_en"),
        "summary": story.get("summary_en"),
        "why_good": story.get("why_good"),
        "category": story.get("category"),
        "country": story.get("country"),
        "score": story.get("score"),
        "significance": story.get("significance"),
        "outcome_status": story.get("outcome_status"),
    }, "sources": evidence}

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    return parse_json_text(response.choices[0].message.content or "")


def main():
    editorial = load(EDITORIAL, {})
    generated = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    candidates = list(editorial.get("stories") or [])
    # Also inspect the strongest reserves; verification may reveal that one deserves promotion.
    candidates += [x for x in (editorial.get("reserves") or []) if int(x.get("score") or 0) >= 78]
    candidates = candidates[:MAX_STORIES]

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        OUTPUT.write_text(json.dumps({
            "generated_at": generated, "ai_configured": False, "stories": [],
            "message": "OPENAI_API_KEY unavailable"
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    from openai import OpenAI
    client = OpenAI()
    results = []

    for story in candidates:
        retrieved = [retrieve_source(s) for s in (story.get("sources") or [])[:MAX_SOURCES_PER_STORY]]
        usable = sum(s["status"] == "retrieved" for s in retrieved)
        try:
            assessment = verify_with_ai(client, story, retrieved)
        except Exception as exc:
            assessment = {
                "support": "unavailable",
                "outcome_status": "unclear",
                "evidence_quality": "low",
                "independence": "unclear",
                "verified_headline": story.get("headline_en") or "",
                "verified_summary": "",
                "verification_note": f"AI verification failed: {type(exc).__name__}",
                "publish_recommendation": "reserve",
            }

        results.append({
            "id": story.get("id"),
            "editorial_score": story.get("score"),
            "editorial_decision": story.get("decision"),
            "retrieved_sources": usable,
            "attempted_sources": len(retrieved),
            "source_results": retrieved,
            **assessment,
        })

    counts = {}
    for row in results:
        key2 = row.get("publish_recommendation") or "unknown"
        counts[key2] = counts.get(key2, 0) + 1

    payload = {
        "generated_at": generated,
        "model": MODEL,
        "ai_configured": True,
        "candidate_count": len(candidates),
        "recommendation_counts": counts,
        "stories": results,
        "pilot_note": "Source-retrieval verification pilot; inaccessible/paywalled sources remain uncertain.",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OWOP verification: {len(results)} candidates; recommendations {counts}")


if __name__ == "__main__":
    main()
