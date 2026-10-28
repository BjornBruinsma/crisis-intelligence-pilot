#!/usr/bin/env python3
"""Build static OWOP pilot dashboard from generated JSON."""
import html
import json
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site" / "owop"
DATA = SITE / "data"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def esc(v):
    return html.escape(str(v or ""))


def source_links(story):
    items = []
    for s in story.get("sources", [])[:5]:
        url = str(s.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        items.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(s.get("publisher") or "source")}</a>')
    return " · ".join(items) or "Source links unavailable"


def card(story, verification=None):
    score = int(story.get("score") or 0)
    verification = verification or {}
    support = verification.get("support") or "not_checked"
    recommendation = verification.get("publish_recommendation") or ""
    verified_headline = verification.get("verified_headline") or story.get("headline_en")
    verified_summary = verification.get("verified_summary") or story.get("summary_en")
    badge = {
        "supported": "✓ source-supported",
        "partially_supported": "△ partially supported",
        "unsupported": "✕ unsupported",
        "unavailable": "? source unavailable",
    }.get(support, "verification pending")
    return f"""
    <article class="card">
      <div class="meta"><span>{esc(story.get('country') or 'Global')}</span><span>•</span><span>{esc(story.get('category'))}</span><span class="score">OWOP {score}</span></div>
      <h2>{esc(verified_headline)}</h2>
      <p class="summary">{esc(verified_summary)}</p>
      <div class="verify">{esc(badge)}{(" · " + esc(recommendation)) if recommendation else ""}</div>
      <p class="why"><b>Why this is good news:</b> {esc(story.get('why_good'))}</p>
      <div class="foot"><span>{esc(story.get('confidence'))} confidence · {int(story.get('source_count') or 0)} source(s)</span><span>{source_links(story)}</span></div>
      <details><summary>AI editorial note</summary><p>{esc(story.get('editor_note'))}</p></details>
    </article>"""


def main():
    editorial = load(DATA / "editorial.json", {})
    verification = load(DATA / "verification.json", {})
    verify_map = {str(x.get("id")): x for x in (verification.get("stories") or []) if x.get("id")}
    fetch = load(DATA / "fetch_status.json", {})
    stories = editorial.get("stories") or []
    categories = Counter(s.get("category") or "Other" for s in stories)
    countries = Counter(s.get("country") or "Global" for s in stories)

    if not editorial.get("ai_configured"):
        body = """
        <section class="empty"><h2>AI editorial board is ready</h2>
        <p>The discovery pipeline is collecting stories. Add the repository secret <code>OPENAI_API_KEY</code> to enable autonomous scoring, translation and publishing.</p></section>"""
    elif not stories:
        body = "<section class='empty'><h2>No stories passed the publish threshold in this run.</h2><p>That is allowed: OWOP should prefer silence over weak good-news claims.</p></section>"
    else:
        body = "".join(card(s, verify_map.get(str(s.get("id")))) for s in stories)

    chips = "".join(f"<span class='chip'>{esc(k)} {v}</span>" for k, v in categories.most_common())
    geo = " · ".join(f"{esc(k)} {v}" for k, v in countries.most_common(8)) or "No published geography yet"
    generated = esc(editorial.get("generated_at") or "not yet")
    candidate_groups = int(editorial.get("candidate_groups") or 0)
    retained = int(fetch.get("retained_urls") or 0)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>One World. One People. — AI news pilot</title>
<style>
:root{{--ink:#17211b;--muted:#68736c;--paper:#f7f8f4;--card:#fff;--line:#e1e6df;--accent:#2d6a4f;--soft:#e9f3ed}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header{{background:#fff;border-bottom:1px solid var(--line)}}.wrap{{max-width:1050px;margin:auto;padding:0 22px}}
.hero{{padding:54px 0 32px}}h1{{font-family:Georgia,serif;font-size:clamp(36px,7vw,72px);line-height:.98;margin:0;letter-spacing:-2px}}.tag{{font-size:20px;color:var(--accent);margin:16px 0 8px;font-weight:650}}
.sub{{color:var(--muted);max-width:720px}}.stats{{display:flex;gap:12px;flex-wrap:wrap;padding:18px 0 28px}}.stat,.chip{{background:var(--soft);border-radius:999px;padding:7px 12px;font-size:13px}}
main{{padding:28px 0 70px}}.section-title{{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:18px}}.section-title h3{{margin:0;font-size:15px;text-transform:uppercase;letter-spacing:.13em}}.geo{{font-size:12px;color:var(--muted)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px;margin:0 0 16px;box-shadow:0 8px 30px rgba(32,55,39,.035)}}.verify{{display:inline-block;margin:2px 0 8px;padding:4px 8px;border-radius:999px;background:#eef2ed;color:var(--muted);font-size:12px}}.meta{{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.07em}}.score{{margin-left:auto;background:var(--soft);color:var(--accent);padding:4px 8px;border-radius:999px;font-weight:700}}h2{{font-family:Georgia,serif;font-size:28px;line-height:1.15;margin:12px 0}}.summary{{font-size:17px}}.why{{background:#fafcf9;border-left:3px solid var(--accent);padding:10px 13px}}.foot{{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px}}a{{color:var(--accent)}}details{{margin-top:12px;color:var(--muted);font-size:12px}}summary{{cursor:pointer}}.empty{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:28px}}code{{background:#edf0ec;padding:2px 5px;border-radius:5px}}
.pilot{{margin-top:32px;border-top:1px solid var(--line);padding-top:20px;color:var(--muted);font-size:12px}}
@media(max-width:600px){{.hero{{padding-top:36px}}h2{{font-size:24px}}.card{{padding:19px}}}}
</style></head><body>
<header><div class="wrap hero"><h1>ONE WORLD.<br>ONE PEOPLE.</h1><div class="tag">Good things are happening everywhere.</div><p class="sub">An autonomous AI news pilot discovering positive, verifiable developments from sources around the world — without politics, doomscrolling or feel-good fluff.</p>
<div class="stats"><span class="stat">{retained} source items retained</span><span class="stat">{candidate_groups} candidate story groups</span><span class="stat">{len(stories)} published this run</span><span class="stat">Updated {generated}</span></div>{chips}</div></header>
<main><div class="wrap"><div class="section-title"><h3>Latest positive developments</h3><div class="geo">{geo}</div></div>{body}
<div class="pilot"><b>Pilot 0.2:</b> AI editorial selection plus source-retrieval verification for the strongest candidates. Verification can remain uncertain when sources are inaccessible, duplicated or paywalled. Source links are provided for inspection.</div></div></main></body></html>"""
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(f"Built OWOP page with {len(stories)} stories")


if __name__ == "__main__":
    main()
