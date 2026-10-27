#!/usr/bin/env python3
"""Render browsable static news HTML; works without JavaScript or data fetches."""
import datetime as dt
import html
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "site"
DATA = ROOT / "data"

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def esc(value):
    return html.escape(str(value or ""), quote=True)

def safe_url(value):
    url = str(value or "")
    p = urlparse(url)
    return url if p.scheme in ("https", "http") and p.netloc else "#"

def main():
    feed = read_json(DATA / "articles.json", {"articles": []})
    status = read_json(DATA / "fetch_status.json", {})
    articles = feed.get("articles") or []
    sources = status.get("sources") or {}
    rss = sources.get("google_news_rss") or {}
    gdelt = sources.get("gdelt_doc2") or {}
    run_time = status.get("last_attempt_utc") or "nog geen uitvoering"
    updated = feed.get("last_success_utc") or "nog geen resultaten"
    total = len(articles)
    categories = sorted({str(c) for a in articles for c in (a.get("topic") or [])})
    sections = []
    for record in articles[:1000]:
        link = safe_url(record.get("url"))
        headline = esc(record.get("title") or "Zonder titel")
        source = esc(record.get("publisher") or record.get("domain") or "onbekende uitgever")
        when = esc(record.get("published_at") or record.get("first_seen") or "")
        provider = "Google Nieuws RSS" if record.get("provider") == "google_news_rss" else "GDELT"
        tags = ", ".join(esc(x) for x in record.get("topic", []))
        filter_values = " ".join(record.get("topic") or [])
        sections.append(
            '<article class="article" data-category="' + esc(filter_values) + '">'
            '<a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">' + headline + '</a>'
            '<div class="meta">' + when + ' · ' + source + ' · ' + esc(provider) + '</div>'
            '<div class="tags">' + tags + '</div></article>'
        )
    article_html = "\n".join(sections) or '<p class="empty">Er staan nog geen artikelen in het nieuwsarchief.</p>'
    options = '<option value="">Alle categorieën</option>' + "".join(
        '<option value="' + esc(c) + '">' + esc(c) + '</option>' for c in categories)
    errors = status.get("errors") or {}
    error_msg = (
        '<p class="warning">Databronnen zijn gedeeltelijk uitgevallen: ' +
        esc(", ".join(errors.keys())) + '. RSS kan wel blijven werken.</p>'
        if errors else "")
    page = f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CRISIS Intelligence — Nieuwsarchief</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0a1422;color:#ecf5ff;font:15px/1.55 system-ui,-apple-system,Arial,sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:28px 18px}}
a{{color:#77d6ff}} h1{{font-size:32px;margin:8px 0}} h2{{font-size:18px}}
.head{{margin-bottom:20px}} .muted,.meta{{color:#abc1d8;font-size:13px}}
.stats{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}}
.stat{{background:#1a314a;border:1px solid #3b5673;border-radius:9px;padding:9px 14px}}
strong{{color:#f2f9ff}}
.warning{{background:#503719;padding:10px;border-radius:7px}}
select{{padding:9px;background:#203952;color:#fff;border:1px solid #5b728a;border-radius:8px}}
.article{{padding:13px 2px;border-bottom:1px solid #33455e}}
.article a{{font-size:16px;font-weight:600}}
.tags{{color:#9ab3c9;font-size:12px}}
.small{{font-size:12px;color:#a4bfd4}}
</style></head><body><main>
<div class="head"><a href="./">← Terug naar de drie meters</a>
<h1>Wereldnieuws — bronarchief</h1>
<p class="muted">Geautomatiseerd verzamelde artikelverwijzingen. Nog geen geverifieerde gebeurtenissen en geen oorlogskansscores.</p>
<div class="stats">
<div class="stat"><strong>{total}</strong> opgeslagen artikelen</div>
<div class="stat"><strong>{rss.get('ok',0)}/{rss.get('total',12)}</strong> Google Nieuws-feeds</div>
<div class="stat"><strong>{gdelt.get('ok',0)}/{gdelt.get('total',2)}</strong> GDELT-zoekopdrachten</div>
</div>
<p class="small">Laatste verzameling: {esc(run_time)} · Laatste gegevensupdate: {esc(updated)} · Status: {esc(status.get('status') or 'onbekend')}</p>
{error_msg}
<p class="small"><strong>Let op:</strong> dit archief bevat koppen en links, geen bewijs dat de beschreven gebeurtenissen hebben plaatsgevonden. Meerdere artikelen kunnen één gebeurtenis beschrijven.</p></div>
<label for="category">Filter op onderwerp:</label> <select id="category">{options}</select>
<h2>Recentste berichten</h2>
<section id="items">{article_html}</section>
<script>
const sel=document.getElementById('category');
sel.addEventListener('change',()=>{{
const target=sel.value;
for(const el of document.querySelectorAll('.article')){{
el.hidden=!!target && !(el.dataset.category||'').includes(target);
}}
}});
</script>
<p class="small">Er worden maximaal 1000 recente links getoond. Het volledige archief staat in <a href="data/articles.json">articles.json</a>.</p>
</main></body></html>"""
    (ROOT / "news.html").write_text(page, encoding="utf-8")
    print(f"Static news page: {total} records, {len(sections)} displayed, {len(page.encode('utf-8'))} bytes")

if __name__ == "__main__":
    main()
