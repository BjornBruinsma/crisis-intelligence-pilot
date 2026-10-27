#!/usr/bin/env python3
"""Create a daily *human-review* shortlist, not verified event facts.

Source input is unverified news *headline groups*. This code does not perform
semantic event extraction and does not calculate conflict risks.
"""
import collections
import datetime as dt
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / "site"
DATA = ROOT / "data"
LIMIT = 25

THEMES = [
    "Militair & veiligheid",
    "Politiek & diplomatie",
    "Overheden & crisismaatregelen",
    "Financiële markten",
    "Energie & grondstoffen",
    "Wereldhandel & logistiek",
    "Bedrijfsleven & investeringen",
    "Economie & samenleving",
]
REGIONAL = "Regionale perspectieven"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def safe_url(value):
    try:
        x = urlsplit(str(value or ""))
        return str(value) if x.scheme in ("http", "https") and x.netloc else "#"
    except ValueError:
        return "#"


def classify(group):
    tags = group.get("categories") or []
    matches = [x for x in THEMES if x in tags]
    # Do not misrepresent a regional search as a proven source country.
    return matches[0] if matches else REGIONAL


def shortlist(groups, count=LIMIT):
    # High/medium category-balanced sampling, not ML and not risk scoring.
    # The current queue is already priority-sorted by scripts/triage.py.
    candidates = [g for g in groups if g.get("priority_level", 0) >= 2]
    groups_by_theme = collections.defaultdict(list)
    for group in candidates:
        groups_by_theme[classify(group)].append(group)
    categories = THEMES + [REGIONAL]
    output = []
    chosen = set()
    # True round robin prevents the highest-volume search locale from
    # dominating while still filling unused category slots.
    while len(output) < count:
        made_progress = False
        for category in categories:
            picked = next((g for g in groups_by_theme[category]
                           if g.get("key") not in chosen), None)
            if picked is None:
                continue
            made_progress = True
            chosen.add(picked["key"])
            output.append({
            "id": picked["key"],
            "headline_claim": picked["title"],
            "discovered_via": classify(picked),
            "other_search_labels": picked.get("categories") or [],
            "publication_day": picked.get("day") or "",
            "publication_day_is_event_date": False,
            "editorial_priority": picked.get("priority") or "",
            "editorial_reason": picked.get("priority_explanation") or "",
            "article_count": picked.get("article_count", 0),
            "publisher_names": picked.get("publishers") or [],
            "independent_corrob_count": None,
            "verification_status": "unreviewed",
            "primary_evidence_confirmed": False,
            "named_event_actor": None,
            "claimed_event_action": None,
            "event_date": None,
            "possible_same_event_ids": [],
            "sources": [
                {
                    "title": a.get("title"),
                    "url": safe_url(a.get("url")),
                    "publisher": a.get("publisher") or a.get("domain"),
                    "published_at": a.get("published_at") or "",
                    "source_provider": a.get("provider") or "",
                }
                for a in (picked.get("articles") or [])[:15]
            ],
            })
            if len(output) >= count:
                break
        if not made_progress:
            break
    return output


def html_page(briefing):
    items = briefing["candidates"]
    cards = []
    for index, item in enumerate(items, 1):
        links = []
        for source in item["sources"]:
            label = html.escape(str(source.get("publisher") or "Uitgever onbekend"))
            name = html.escape(str(source.get("title") or "Bron"))
            url = html.escape(safe_url(source.get("url")), quote=True)
            links.append(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">'
                         f'{name}</a><small> · {label}</small></li>')
        gid = html.escape(item["id"], quote=True)
        title = html.escape(item["headline_claim"])
        theme = html.escape(item["discovered_via"])
        day = html.escape(item["publication_day"])
        cards.append(f"""<article class="candidate" data-id="{gid}">
<div class="meta">#{index} · {theme} · gepubliceerd {day} · {item["article_count"]} artikelen</div>
<h3>{title}</h3>
<p class="fine">Let op: dit is een berichtclaim, niet een vastgesteld feit. De publicatiedatum is niet noodzakelijk de gebeurtenisdatum.</p>
<details><summary>Bekijk bronnen ({len(item["sources"])})</summary><ul>{"".join(links)}</ul></details>
<div class="fields">
<label>Beoordeling
<select class="assessment">
<option value="unreviewed">Nog niet beoordeeld</option>
<option value="investigate">Verder onderzoeken</option>
<option value="duplicate">Mogelijk dezelfde gebeurtenis</option>
<option value="not_relevant">Niet relevant</option>
<option value="needs_primary_source">Primaire bron nodig</option>
</select></label>
<label>Korte omschrijving van de te controleren claim
<textarea class="claim" rows="2" placeholder="Wat is de concrete handeling, door wie en waar?"></textarea></label>
<label>Primaire bron-URL (optioneel)
<input class="primary" type="url" placeholder="https://..."></label>
<label>Opmerkingen / verwijzing naar andere gebeurtenis
<textarea class="notes" rows="2" placeholder="Welke feiten ontbreken? Wat spreekt het tegen?"></textarea></label>
</div></article>""")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRISIS Intelligence — Verification Desk</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{font:15px/1.5 system-ui,Arial,sans-serif;margin:0;background:#0a1422;color:#eff6ff}}
main{{max-width:1000px;padding:22px 16px;margin:auto}}a{{color:#77d7ff}}
h1{{font-size:30px}}h3{{font-size:17px;margin:9px 0}}
.muted,.fine,.meta,small{{color:#aec2d6;font-size:12px}}
.notice{{background:#28374b;padding:12px;border-left:3px solid #f0b569;border-radius:6px}}
.candidate{{background:#15283b;border:1px solid #3a526e;border-radius:12px;margin:15px 0;padding:17px}}
select,input,textarea{{font:inherit;background:#0f2133;color:#fff;border:1px solid #4c6480;border-radius:7px;padding:9px;width:100%}}
textarea{{resize:vertical}}.fields{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:15px}}
label{{display:block;font-size:12px;color:#cbd8e5}}label>*{{margin-top:5px}}
summary{{cursor:pointer;color:#8bd7fd}}li{{padding:3px 0}}
.controls{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0}}
button{{cursor:pointer;border-radius:8px;padding:10px 14px;background:#147da5;color:white;border:0;font-weight:650}}
button.secondary{{background:#26415b}}
@media(max-width:680px){{.fields{{grid-template-columns:1fr}}}}
</style></head><body><main>
<a href="./">← Dashboard</a> · <a href="./review.html">Volledige redactiewachtrij</a>
<h1>Verification Desk</h1><p>Dagelijkse controlelijst: <b>{len(items)} kandidaten</b>, uit {briefing["source_groups_count"]} voorlopige titelgroepen.</p>
<p class="notice"><strong>Geen AI-factcheck:</strong> deze selectie gebruikt uitsluitend nieuwsmetadata en eenvoudige sorteerregels. Iedere kop is een nog onbewezen claim. Bronuitgevers zijn niet noodzakelijk onafhankelijk. Beoordelingen blijven lokaal in deze browser en veranderen de publieke meters niet.</p>
<div class="controls"><button id="export">Exporteer mijn beoordelingen (JSON)</button>
<button class="secondary" id="clear">Wis lokale beoordelingen</button></div>
<p class="fine">Export is bedoeld voor afzonderlijke broncontrole. Deel het JSON-bestand niet publiekelijk als het gevoelige notities bevat. Na export kunnen we de gecontroleerde bevindingen in GitHub verwerken.</p>
<div id="candidates">{"".join(cards) if cards else "<p>Geen kandidaten beschikbaar.</p>"}</div>
<script>
const STORAGE = "crisis-intelligence-verification-local-v1";
const snapshot = {json.dumps([x["id"] for x in items], ensure_ascii=False)};
function collect(){{
  return [...document.querySelectorAll('.candidate')].map(el=>({{
    id:el.dataset.id,
    assessment:el.querySelector('.assessment').value,
    claim:el.querySelector('.claim').value,
    primary_source_url:el.querySelector('.primary').value,
    notes:el.querySelector('.notes').value
  }}));
}}
function save(){{try{{localStorage.setItem(STORAGE,JSON.stringify(collect()));}}catch(_e){{}}}}
try{{
  const previous=JSON.parse(localStorage.getItem(STORAGE)||"[]");
  const byId=new Map(previous.map(item=>[item.id,item]));
  document.querySelectorAll('.candidate').forEach(el=>{{
    const p=byId.get(el.dataset.id);
    if(!p)return;
    el.querySelector('.assessment').value=p.assessment||'unreviewed';
    el.querySelector('.claim').value=p.claim||'';
    el.querySelector('.primary').value=p.primary_source_url||'';
    el.querySelector('.notes').value=p.notes||'';
  }});
}}catch(_e){{}}
document.getElementById('candidates').addEventListener('input',save);
document.getElementById('candidates').addEventListener('change',save);
document.getElementById('export').addEventListener('click',()=>{{
  const out={{generated_for: 'CRISIS verification', exported_at:new Date().toISOString(),
    meaning:'Unverified human annotations only; not publicly confirmed facts',
    selections:collect()}};
  const url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{{type:'application/json'}}));
  const a=document.createElement('a');
  a.href=url;a.download='crisis-verification-annotations.json';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
}});
document.getElementById('clear').addEventListener('click',()=>{{
  if(!confirm('Lokale notities in deze browser wissen?'))return;
  try{{localStorage.removeItem(STORAGE)}}catch(_e){{}}
  location.reload();
}});
</script>
</main></body></html>"""


def main():
    queue=load(DATA/"review_queue.json", {"groups":[]})
    selected=shortlist(queue.get("groups") or [])
    digest={
        "description":"Manually reviewable headline claims; no event verification, no risk scoring",
        "source_generated_from":queue.get("generated_from"),
        "source_groups_count":len(queue.get("groups") or []),
        "selection_method":"Category-balanced high/medium editorial candidates; NOT trained or calibrated",
        "candidates":selected
    }
    (DATA/"verification_candidates.json").write_text(
        json.dumps(digest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"verify.html").write_text(html_page(digest),encoding="utf-8")
    counts=collections.Counter(x["discovered_via"] for x in selected)
    print(f"Verification Desk: {len(selected)} candidates from {digest['source_groups_count']} story groups; by category {dict(counts)}")


if __name__ == "__main__":
    main()
