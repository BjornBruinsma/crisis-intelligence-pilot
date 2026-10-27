#!/usr/bin/env python3
"""Generate a reproducible, review-only story candidate queue from headline metadata.

NOT event extraction: identical/similar articles may mention several actual events.
Clusters are provisional story groups. Priority is editorial triage, never war risk.
"""
import collections
import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
DATA = SITE / "data"
MAX_CANDIDATES = 600
TOP_DISPLAY = 180
ACTION_WORDS = [
    "evacuat", "withdraw", "depart", "pulls staff", "ordered", "order to leave",
    "deploy", "mobiliz", "bomb", "missile", "drone", "attack", "airstrike",
    "strike", "ceasefire", "negotiat", "sanction", "mediati", "agreement",
    "suspend", "cancel", "halt", "blockade", "closed", "closure", "shut",
    "pipeline", "tanker", "refiner", "oil supply", "insurance", "premium",
    "military", "naval", "ultimatum", "threaten", "production",
    "停火", "袭击", "军事", "谈判", "撤离", "航母", "石油", "导弹",
    "هجوم", "ضربة", "صواريخ", "إجلاء", "محادثات", "وقف إطلاق النار",
    "تهديد", "النفط", "إيران", "السعودية", "جنگ", "حمله", "توافق",
]
RELEVANT_WORDS = [
    "iran", "hormuz", "tehran", "israel", "saudi", "riyadh", "houthis",
    "houthi", "gulf", "middle east", "oil", "lng", "brent", "diesel",
    "shipping", "tanker", "opec", "pakistan", "qatar", "dubai", "iraq",
    "إيران", "هرمز", "السعودية", "الخليج", "النفط", "伊朗", "霍尔木兹", "石油",
    "ایران", "هرمز",
]
LOW_SIGNAL = [
    "canelo", "wwe", "boxing", "football", "soccer", "crown jewel",
    "horoscope", "celebrity", "astrology", "match preview",
]
SOURCE_ALIASES = {"https://www.thetraveler.org/": "thetraveler.org",
                  "www.thetraveler.org": "thetraveler.org"}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def normalized(title):
    title = unicodedata.normalize("NFKC", str(title or "")).casefold()
    # Remove trailing publication label on most Google News titles.
    title = re.sub(r"\s+[-–—]\s+[^-–—]{1,85}$", "", title)
    title = "".join(c for c in unicodedata.normalize("NFKD", title)
                    if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", title, flags=re.UNICODE).strip()


def tokens(title):
    return {word for word in normalized(title).split() if len(word) >= 3}


def sim(a, b):
    aa, bb = tokens(a), tokens(b)
    if min(len(aa), len(bb)) < 4:
        return 1.0 if normalized(a) == normalized(b) else 0.0
    common = len(aa & bb)
    return common / (len(aa) + len(bb) - common)


def editorial_rank(article):
    t = str(article.get("title") or "").casefold()
    relevant = any(word in t for word in RELEVANT_WORDS)
    action = any(word in t for word in ACTION_WORDS)
    entertainment = any(word in t for word in LOW_SIGNAL)
    if entertainment:
        return 0, "Entertainment / zijdelings relevant; redactionele controle"
    if relevant and action:
        return 3, "Relevante regio/markt + mogelijke concrete actie"
    if relevant:
        return 2, "Relevante regio/markt; aard van ontwikkeling controleren"
    if action:
        return 1, "Actie genoemd, maar verband met de crisis onzeker"
    return 0, "Geen duidelijk criseslement in de kop"


def canonical_publisher(row):
    raw = str(row.get("publisher") or row.get("domain") or "onbekend").strip()
    return SOURCE_ALIASES.get(raw, raw).casefold()


def date_bucket(row):
    return str(row.get("published_at") or row.get("first_seen") or "")[:10]


def cluster_articles(articles):
    """Cluster near-identical same-day *headlines*, not independently verify events."""
    clusters = []
    buckets = collections.defaultdict(list)
    for article in sorted(articles,
                          key=lambda a: a.get("published_at") or a.get("first_seen") or "",
                          reverse=True):
        title = article.get("title") or ""
        if not title.strip():
            continue
        day = date_bucket(article)
        group = None
        # 0.80 is deliberately conservative; false merging can hide distinct events.
        for idx in buckets[day]:
            candidate = clusters[idx]
            if sim(candidate["title"], title) >= 0.80:
                group = candidate
                break
        if group is None:
            group = {"title": title, "articles": [], "day": day}
            buckets[day].append(len(clusters))
            clusters.append(group)
        group["articles"].append(article)

    for group in clusters:
        rows = group["articles"]
        ranks = [editorial_rank(a) for a in rows]
        level = max(r[0] for r in ranks)
        publishers = sorted({canonical_publisher(a) for a in rows})
        group["priority"] = ("hoog" if level == 3 else "middel" if level == 2 else "laag")
        group["priority_level"] = level
        group["priority_explanation"] = next(reason for v, reason in ranks if v == level)
        group["publishers"] = publishers
        group["article_count"] = len(rows)
        group["source_count"] = len(publishers)
        group["categories"] = sorted({str(topic) for a in rows for topic in (a.get("topic") or [])})
        group["key"] = hashlib.sha256(
            (group["day"] + ":" + normalized(group["title"])).encode("utf-8")
        ).hexdigest()[:14]
        group["review_status"] = "unverified_story_candidate"
        # Editorial ordering only, no score contributions.
        group["review_order"] = level * 10 + min(3, len(publishers) - 1)
    clusters.sort(key=lambda g:(g["review_order"], g["day"]),reverse=True)
    return clusters


def clean_url(value):
    from urllib.parse import urlsplit
    url = str(value or "")
    parsed = urlsplit(url)
    return url if parsed.scheme in ("http", "https") and parsed.netloc else "#"


def make_html(queue, stats):
    rows = []
    for group in queue[:TOP_DISPLAY]:
        evidence = []
        for article in group["articles"][:10]:
            url = html.escape(clean_url(article.get("url")), quote=True)
            title = html.escape(str(article.get("title") or ""),quote=False)
            pub = html.escape(str(article.get("publisher") or article.get("domain") or "bron onbekend"))
            evidence.append(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a> '
                            f'<span class="sub">({pub})</span></li>')
        priority = group["priority"]
        badge = "p-high" if priority == "hoog" else "p-mid" if priority == "middel" else "p-low"
        rows.append(
            f'<article class="story" data-priority="{priority}">'
            f'<div class="line"><span class="flag {badge}">{priority.upper()}</span>'
            f'<span class="sub">{html.escape(group["day"])} · '
            f'{group["article_count"]} artikel(en) · {group["source_count"]} uitgever(s)</span></div>'
            f'<h3>{html.escape(group["title"])}</h3>'
            f'<p class="sub">{html.escape(group["priority_explanation"])} · '
            'TITELGROEP, GEEN BEVESTIGDE GEBEURTENIS</p>'
            f'<details><summary>Bekijk bronartikelen en zoeklabels</summary><ul>{"".join(evidence)}</ul>'
            f'<div class="sub">{html.escape(" · ".join(group["categories"]))}</div>'
            f'</details></article>')
    counts = stats["priority_counts"]
    note = "Publicaties van dezelfde nieuwsorganisatie of persbureau zijn geen onafhankelijke bevestigingen."
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CRISIS Intelligence — Redactiewachtrij</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{background:#0a1422;color:#edf6ff;font:15px/1.5 system-ui;margin:0}}
main{{max-width:1040px;margin:0 auto;padding:24px 16px}}
a{{color:#7dd3ff}}.sub{{color:#a9c0d6;font-size:12px}}h1{{margin:12px 0}}h3{{margin:6px 0;font-size:16px}}
.stats{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}}
.metric{{padding:10px 16px;background:#1a324a;border:1px solid #385372;border-radius:10px}}
.story{{padding:17px;border:1px solid #36506c;background:#15283d;border-radius:12px;margin:12px 0}}
.line{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}.flag{{font-size:11px;font-weight:700;border-radius:5px;padding:2px 8px}}
.p-high{{background:#653e27;color:#ffe3cb}}.p-mid{{background:#4c4a2c;color:#fff2b9}}.p-low{{background:#2b4353;color:#d6e8ff}}
summary{{cursor:pointer;color:#8edaff}}li{{margin:5px 0}}select{{padding:9px;background:#1d344a;border:1px solid #486480;color:#fff;border-radius:8px}}
.warning{{background:#342f25;border-left:3px solid #d6a35a;padding:12px}}
</style></head><body><main><a href="./">← Dashboard</a> · <a href="./news.html">Alle artikelen</a>
<h1>Redactiewachtrij</h1>
<p>Automatisch gegroepeerde <b>nieuwskoppen</b>, gesorteerd op redactionele urgentie. 
Dit zijn géén geverifieerde gebeurtenissen en de prioriteit is géén oorlogskans.</p>
<div class="stats"><div class="metric"><b>{stats["article_count"]}</b> artikelen</div>
<div class="metric"><b>{stats["group_count"]}</b> voorlopige titelgroepen</div>
<div class="metric"><b>{counts.get("hoog",0)}</b> hoog</div>
<div class="metric"><b>{counts.get("middel",0)}</b> middel</div>
<div class="metric"><b>{counts.get("laag",0)}</b> laag</div></div>
<p class="warning">{html.escape(note)} Meertalige parafrases kunnen nog afzonderlijk voorkomen. 
Een artikel kan meer dan één gebeurtenis beschrijven. Een hoge prioriteit betekent alleen: eerst beoordelen.</p>
<label for="priority">Filter prioriteit</label> <select id="priority">
<option value="">Alle niveaus</option><option value="hoog">Hoog</option>
<option value="middel">Middel</option><option value="laag">Laag</option></select>
<p class="sub">De eerste {min(len(queue),TOP_DISPLAY)} kandidaten; volledige machineleesbare queue in
<a href="./data/review_queue.json">review_queue.json</a>.</p>
<section id="stories">{"".join(rows)}</section>
<script>const p=document.getElementById('priority');p.onchange=()=>{{for(const x of document.querySelectorAll('.story'))
x.hidden=!!p.value&&x.dataset.priority!==p.value;}};</script>
</main></body></html>"""


def main():
    feed = load(DATA / "articles.json", {"articles": []})
    articles = list(feed.get("articles") or [])[:MAX_CANDIDATES]
    groups = cluster_articles(articles)
    priorities = collections.Counter(g["priority"] for g in groups)
    stats = {"article_count":len(articles), "group_count":len(groups),
             "priority_counts":dict(priorities),
             "groups_with_repeated_headlines":sum(g["article_count"]>1 for g in groups),
             "note":"Conservative same-day headline similarity, not semantic event clustering"}
    store = {"generated_from":feed.get("last_success_utc"),
             "description":"Unverified title clusters; priority for human editorial review only",
             "stats":stats, "groups":groups}
    (DATA/"review_queue.json").write_text(json.dumps(store,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (SITE/"review.html").write_text(make_html(groups,stats),encoding="utf-8")
    print("Triage: "+str(stats))


if __name__=="__main__":
    main()
