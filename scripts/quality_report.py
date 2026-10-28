#!/usr/bin/env python3
"""Publish operational QA metrics from saved source artifacts, not claims of accuracy.

Coverage and technical consistency are measurable. True event precision and
source verification accuracy cannot be established without a labeled test set.
"""
import collections
import datetime as dt
import html
import json
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]/"site"
DATA=SITE/"data"
OUT=DATA/"quality_report.json"

def read(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return default

def esc(val):
    return html.escape(str(val or ""),quote=True)

def main():
    feed=read(DATA/"articles.json",{"articles":[]})
    queue=read(DATA/"review_queue.json",{"groups":[]})
    selection=read(DATA/"verification_candidates.json",{"candidates":[]})
    assessment=read(DATA/"ai_assessments.json",{"assessments":{}})
    events=read(DATA/"event_candidates.json",{"events":[]})
    sources=read(DATA/"primary_sources.json",{"sources":[]})
    source_status=read(DATA/"fetch_status.json",{})
    articles=feed.get("articles") or []
    groups=queue.get("groups") or []
    selected=selection.get("candidates") or []
    checked=assessment.get("assessments") or {}
    output=events.get("events") or []
    official=sources.get("sources") or []
    matched=[x for x in output if x.get("primary_evidence")]
    direct=[x for x in matched if x["primary_evidence"].get("relation")=="supports_specific_claim"]
    contradiction=[x for x in matched if x["primary_evidence"].get("relation")=="contradicts_specific_claim"]
    factual_status=collections.Counter(x.get("research_status") or "unknown" for x in output)
    issues=[]
    input_ids={x.get("id") for x in selected if x.get("id") and
               (checked.get(x.get("id"),{}).get("relevance")!="irrelevant")}
    output_ids=[gid for x in output for gid in x.get("headline_claim_ids") or []]
    if not output:issues.append("Geen groepresultaten gegenereerd")
    if set(output_ids)!=input_ids or len(set(output_ids))!=len(output_ids):
        issues.append("Een of meer bronclaim-ID's ontbreekt of komt dubbel voor")
    if events.get("status")!="complete":
        issues.append("AI-gebeurtenisverwerking niet volledig: "+str(events.get("status")))
    if not direct:
        issues.append("Geen specifieke officiële ondersteuning automatisch aangetroffen")
    failed=[x.get("id") for x in official if x.get("status")!="ok"]
    if failed:issues.append("Officiële bronnen onvolledig: "+", ".join(map(str,failed)))
    match_verified=sum(x.get("verified_event") is True for x in output)
    if match_verified:issues.append("VEILIGHEIDSFOUT: kandidaat ten onrechte als bevestigd gemarkeerd")
    model_metric=events.get("clustering_metrics") or {}
    report={
      "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "definition":"Automatische procescontrole, geen wetenschappelijke validatie van gebeurteniswaarheid.",
      "technical":{
        "collected_articles":len(articles),
        "tentative_headline_groups":len(groups),
        "daily_shortlist":len(selected),
        "ai_reviewed_shortlist":sum(x.get("id") in checked for x in selected),
        "ai_headline_status":assessment.get("status"),
        "event_research_status":events.get("status"),
        "event_input_claims":events.get("input_candidate_count",0),
        "event_groups_output":len(output),
        "multiple_claim_clusters":sum(len(x.get("headline_claim_ids") or [])>1 for x in output),
        "claims_in_multiple_claim_clusters":sum(len(x.get("headline_claim_ids") or [])
                                      for x in output if len(x.get("headline_claim_ids") or [])>1),
        "ids_retained_without_duplicates":set(output_ids)==input_ids and len(output_ids)==len(set(output_ids)),
        "official_sources_checked":len(official),
        "official_sources_accessible":sum(x.get("status")=="ok" for x in official),
        "official_exact_passage_matches":len(matched),
        "potential_direct_support_matches":len(direct),
        "potential_contradictions":len(contradiction),
        "verified_events":0,
        "clustering_method":events.get("clustering_method") or "unknown",
        "proposed_merge_pairs":model_metric.get("model_pair_proposals"),
        "accepted_merge_connections":model_metric.get("accepted_pair_connections"),
        "rejected_merge_proposals":model_metric.get("rejected_pair_proposals"),
        "rss_profiles_ok":(source_status.get("sources") or {}).get("google_news_rss",{}).get("ok"),
        "gdelt_queries_ok":(source_status.get("sources") or {}).get("gdelt_doc2",{}).get("ok"),
      },
      "source_breakdown":[{"authority":x.get("authority"),"id":x.get("id"),
                           "status":x.get("status"),"passages":len(x.get("passages") or []),
                           "links":len(x.get("links") or [])} for x in official],
      "research_status_breakdown":dict(factual_status),
      "uncertainty":{
        "true_cluster_precision":None,
        "true_cluster_recall":None,
        "actual_missed_events":None,
        "verified_incident_count":None,
        "reason":"Er ontbreekt een onafhankelijke, handmatig geannoteerde gouden testset; modelconsensus is geen grondwaarheid.",
      },
      "warnings":issues,
    }
    # No guarantee that the analysis is accurate; never render absent metrics as 100%.
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    t=report["technical"]
    rows=[
      ("Verzamelde artikelen",t["collected_articles"]),
      ("Voorlopige kopgroepen",t["tentative_headline_groups"]),
      ("Geselecteerde claims",t["daily_shortlist"]),
      ("AI-beoordeelde claims",t["ai_reviewed_shortlist"]),
      ("Geanalyseerde claim-ID's",t["event_input_claims"]),
      ("Gebeurteniskandidaatgroepen",t["event_groups_output"]),
      ("Groepen met meerdere claims",t["multiple_claim_clusters"]),
      ("Alle claim-ID's zonder verlies bewaard", "JA" if t["ids_retained_without_duplicates"] else "NEE"),
      ("Geaccepteerde AI-samenvoegingen",t["accepted_merge_connections"] if t["accepted_merge_connections"] is not None else "Niet beschikbaar"),
      ("Afgewezen AI-samenvoegingen",t["rejected_merge_proposals"] if t["rejected_merge_proposals"] is not None else "Niet beschikbaar"),
      ("Bereikbare officiële bronnen",f"{t['official_sources_accessible']}/{t['official_sources_checked']}"),
      ("Letterlijke officiële tekstmatches",t["official_exact_passage_matches"]),
      ("Mogelijk direct ondersteunende passages",t["potential_direct_support_matches"]),
    ]
    table="".join("<tr><td>"+esc(a)+"</td><td>"+esc(b)+"</td></tr>" for a,b in rows)
    alerts="".join("<li>"+esc(x)+"</li>" for x in issues) or "<li>Geen technische waarschuwingen in deze meting.</li>"
    breakdown="".join("<tr><td>"+esc(x.get("authority"))+"</td><td>"+esc(x.get("status"))+"</td><td>"+str(x["passages"])+"</td><td>"+str(x["links"])+"</td></tr>" for x in report["source_breakdown"])
    page=f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRISIS Intelligence — Kwaliteitscontrole</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{font:15px/1.5 system-ui;background:#0a1422;color:#eef7ff;margin:0}}
main{{max-width:960px;margin:auto;padding:24px 15px}}a{{color:#87d8ff}}h1{{font-size:30px}}
table{{border-collapse:collapse;width:100%;margin:14px 0 20px}}td,th{{padding:11px;border-bottom:1px solid #344a65;text-align:left}}
td:last-child{{font-variant-numeric:tabular-nums}}h2{{margin-top:28px;font-size:21px}}
.notice{{background:#3a3326;padding:14px;border-left:3px solid #edb866;border-radius:7px}}
.note{{color:#afc4d7;font-size:13px}}.panel{{padding:18px;background:#152a3e;border:1px solid #38526c;border-radius:11px}}
</style></head><body><main>
<a href="./">← Dashboard</a> · <a href="./events.html">Gebeurteniskandidaten</a>
<h1>Kwaliteitscontrole — CRISIS AI</h1>
<p class="notice"><b>Technische consistentie ≠ feitelijke juistheid.</b>
Een volledig verwerkte set of groen vinkje betekent niet dat de samenvoegingen correct zijn.
Echte precisie/recall en aantallen gemiste gebeurtenissen zijn momenteel onbekend.</p>
<div class="panel"><h2>Gecontroleerde procesmetingen</h2><table>{table}</table>
<p class="note">AI-status: {esc(t["ai_headline_status"])} · Gebeurtenisstatus: {esc(t["event_research_status"])}
· Clustermethode: {esc(t["clustering_method"])}</p></div>
<h2>Waarschuwingen</h2><ul>{alerts}</ul>
<h2>Officiële brondekking</h2>
<table><thead><tr><th>Autoriteit</th><th>Bereikbaar</th><th>Passages</th><th>Links</th></tr></thead>
<tbody>{breakdown}</tbody></table>
<p class="note">Een officieel citaat toont wat de autoriteit schrijft, niet dat een
nieuwsclaim objectief is bevestigd. Afwezigheid van passende teksten is geen ontkrachting.</p>
<h2>Wat we nog niet kunnen meten</h2>
<p>De werkelijke nauwkeurigheid van clustering, hoeveel gebeurtenissen gemist
zijn en de precisie van automatische bronmatches vereisen een onafhankelijk
geannoteerde testset. We publiceren daarvoor bewust geen percentages.</p>
<p class="note">Berekend {esc(report["generated_at_utc"])} ·
<a href="./data/quality_report.json">Download machineleesbaar kwaliteitsrapport</a></p>
</main></body></html>"""
    (SITE/"quality.html").write_text(page,encoding="utf-8")
    print(f"QA: {t['event_groups_output']} clusters, {t['multiple_claim_clusters']} combined, "
          f"{t['official_exact_passage_matches']} matched evidence texts, {len(issues)} warnings")

if __name__=="__main__":main()
