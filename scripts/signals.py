#!/usr/bin/env python3
"""Research indicators over unverified headline claims. Not a risk forecast.

Counts are taken from one current 25-item research shortlist, counting each
group only once. They cannot be interpreted as probabilities, frequency of
real-world incidents, or representative news sentiment.
"""
import collections
import datetime as dt
import html
import json
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]/"site"
DATA=SITE/"data"
OUTPUT=DATA/"signals.json"
HISTORY=DATA/"signal_history.json"
DIRECTIONS=("escalation","deescalation","mixed","neutral","unclear")

def load(p,default):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError,OSError):return default

def escape(value):
    return html.escape(str(value or ""),quote=True)

def compute(events,ai,quality,now=None):
    now=now or dt.datetime.now(dt.timezone.utc).isoformat()
    assessed=ai.get("assessments") or {}
    groups=events.get("events") or []
    tally=collections.Counter()
    priority=collections.Counter()
    unassessed=0
    for group in groups:
        members=[assessed.get(x) for x in group.get("headline_claim_ids") or []]
        members=[m for m in members if isinstance(m,dict)]
        if not members:
            unassessed+=1
            tally["unclear"]+=1
            continue
        directions={str(m.get("direction") or "unclear") for m in members}
        # A group with conflicting source directions is mixed, not a
        # majority-vote escalation signal.
        direction=next(iter(directions)) if len(directions)==1 else "mixed"
        if direction not in DIRECTIONS:direction="unclear"
        tally[direction]+=1
        if group.get("editorial_importance")=="high":
            priority[direction]+=1
    metrics=quality.get("technical") or {}
    status=events.get("status")
    is_complete=(status=="complete" and
                 metrics.get("ids_retained_without_duplicates") is True)
    return {
      "updated_at_utc":now,
      "research_status":"headlines_only_unverified",
      "complete":is_complete,
      "cannot_infer_probability":True,
      "sample_size_groups":len(groups),
      "news_direction_groups":{x:tally[x] for x in DIRECTIONS},
      "high_importance_groups":{x:priority[x] for x in DIRECTIONS},
      "groups_without_ai_direction":unassessed,
      "verified_event_count":0,
      "specific_official_matches":metrics.get("potential_direct_support_matches",0),
      "official_sources_accessible":metrics.get("official_sources_accessible",0),
      "official_sources_checked":metrics.get("official_sources_checked",0),
      "clustering_status":status,
      "quality_warnings":quality.get("warnings") or [],
      "method":"One provisional group yields one editorial direction, not one real event.",
    }

def update_history(previous,current,max_len=120):
    # Multiple GitHub updates a day replace that UTC day's snapshot instead
    # of creating a fake timeseries spike from repeated processing.
    day=current["updated_at_utc"][:10]
    records=[v for v in previous if isinstance(v,dict) and
             v.get("day")!=day and v.get("day")]
    records.append({
      "day":day,"complete":current["complete"],
      "sample_size_groups":current["sample_size_groups"],
      "news_direction_groups":current["news_direction_groups"],
      "specific_official_matches":current["specific_official_matches"],
      "note":"Daily shortlist snapshot, NOT actual event frequency",
    })
    records.sort(key=lambda x:x["day"])
    return records[-max_len:]

def render(signals,history):
    d=signals["news_direction_groups"]
    maximum=max(1,max(d.values()))
    labels={"escalation":"Koppen met escalatiesignaal",
            "deescalation":"Koppen met de-escalatiesignaal",
            "mixed":"Gemengde signalen",
            "neutral":"Neutrale signalen","unclear":"Onbekende richting"}
    blocks="".join(
      '<div class="metric"><div class="line"><span>'+escape(labels[k])+
      '</span><b>'+str(d[k])+'</b></div><div class="track"><div class="fill" style="width:'+
      str(round(100*d[k]/maximum))+'%"></div></div></div>'
      for k in DIRECTIONS)
    last=history[-12:]
    rows="".join("<tr><td>"+escape(r["day"])+"</td><td>"+
        str(r["sample_size_groups"])+"</td><td>"+
        str(r["news_direction_groups"].get("escalation",0))+"</td><td>"+
        str(r["news_direction_groups"].get("deescalation",0))+"</td><td>"+
        str(r["specific_official_matches"])+"</td></tr>"
        for r in reversed(last))
    warnings="".join("<li>"+escape(x)+"</li>" for x in signals["quality_warnings"]) or "<li>Geen technische waarschuwingen</li>"
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRISIS — Signaalmonitor (geen kansscores)</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0a1422;color:#eff6ff;font:15px/1.5 system-ui}}
main{{max-width:1040px;margin:auto;padding:25px 16px}}
a{{color:#91dcff}}h1{{font-size:30px}}h2{{font-size:21px;margin:26px 0 12px}}
.notice{{background:#383024;border-left:4px solid #e9af62;padding:15px;border-radius:8px}}
.panel{{background:#15283e;padding:17px;border:1px solid #314b66;border-radius:12px;margin:16px 0}}
.line{{display:flex;justify-content:space-between;gap:15px}}
.metric{{margin:14px 0}}.track{{background:#29394c;height:10px;border-radius:9px;margin-top:5px}}
.fill{{background:#72add3;height:10px;border-radius:9px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #30485f}}
small,.muted{{color:#b7c9d9}}</style></head><body><main>
<a href="./">← Dashboard</a> · <a href="./events.html">Gebeurteniskandidaten</a> · <a href="./quality.html">Kwaliteitscontrole</a>
<h1>Signaalmonitor — onderzoeksdata</h1>
<p class="notice"><b>Dit zijn géén voorspellingen of geverifieerde incidenten.</b>
We tellen voor elke geselecteerde nieuwskopgroep slechts één voorlopige AI-richting.
De steekproef van maximaal 25 kopgroepen is niet representatief voor al het
nieuws. Verandering in de telling kan komen door andere zoekresultaten,
bronbeschikbaarheid of redactionele selectie — niet noodzakelijk door een crisisverandering.
Er worden geen oorlogskansen of economische risicoscores afgeleid.</p>
<div class="panel"><h2>Huidige geselecteerde nieuwssignalen</h2>
<p class="muted">{signals["sample_size_groups"]} claimgroepen · Analyse {'compleet' if signals["complete"] else 'onvolledig'} ·
{escape(signals["updated_at_utc"])}</p>{blocks}</div>
<div class="panel"><h2>Onderbouwing</h2>
<p>Specifieke officiële tekstmatches: <b>{signals["specific_official_matches"]}</b>.
Officiële bronsites bereikbaar: <b>{signals["official_sources_accessible"]}/{signals["official_sources_checked"]}</b>.
Geverifieerde gebeurtenissen: <b>0</b>.</p><ul>{warnings}</ul></div>
<h2>Dagelijkse steekproeven (geen gebeurtenistrend)</h2>
<p class="muted">Tellingen uit afzonderlijke dagselecties zijn niet direct vergelijkbaar; deze tabel is alleen operationele monitoring.</p>
<table><thead><tr><th>UTC-dag</th><th>Groepen</th><th>Escalatie</th><th>De-escalatie</th><th>Officiële matches</th></tr></thead><tbody>
{rows}</tbody></table>
<p><small><a href="./data/signals.json">Signalendata (JSON)</a> ·
<a href="./data/signal_history.json">Dagelijkse snapshots (JSON)</a>.
Feitelijke precisie en calibratie: niet vastgesteld.</small></p>
</main></body></html>"""

def main():
    events=load(DATA/"event_candidates.json",{"events":[]})
    ai=load(DATA/"ai_assessments.json",{"assessments":{}})
    quality=load(DATA/"quality_report.json",{})
    current=compute(events,ai,quality)
    prev=load(HISTORY,{"snapshots":[]})
    history=update_history(prev.get("snapshots") or [],current)
    OUTPUT.write_text(json.dumps(current,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    HISTORY.write_text(json.dumps({"snapshots":history},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (SITE/"signals.html").write_text(render(current,history),encoding="utf-8")
    print(f"Signal monitor: {current['sample_size_groups']} unverified groups; "
          f"complete={current['complete']}; verified=0; daily snapshots={len(history)}")
if __name__=="__main__":main()
