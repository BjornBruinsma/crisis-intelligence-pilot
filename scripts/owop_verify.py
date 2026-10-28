#!/usr/bin/env python3
"""OWOP web verification desk.

For the strongest editorial candidates:
1. use OpenAI's Chat Completions web-search model to find current public sources,
   preferably the original/primary source plus independent reporting;
2. pass the search evidence to a separate verifier model;
3. record support, outcome status, evidence quality and publish recommendation.

This is still a pilot: search can miss sources and independent-looking articles
can repeat the same press release. Uncertainty is recorded rather than hidden.
"""
import datetime as dt
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "site" / "owop"
DATA = ROOT / "data"
EDITORIAL = DATA / "editorial.json"
OUTPUT = DATA / "verification.json"
SEARCH_MODEL = os.getenv("OWOP_SEARCH_MODEL", "gpt-5-search-api")
RESPONSES_SEARCH_MODEL = os.getenv("OWOP_RESPONSES_SEARCH_MODEL", "gpt-6-luna")
VERIFY_MODEL = os.getenv("OWOP_VERIFY_MODEL", "gpt-4o-mini")
MAX_STORIES = 8


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def parse_json_text(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    return json.loads(text)


def annotation_urls(message):
    out = []
    for ann in (getattr(message, "annotations", None) or []):
        citation = getattr(ann, "url_citation", None)
        if citation is None and isinstance(ann, dict):
            citation = ann.get("url_citation")
        if not citation:
            continue
        if isinstance(citation, dict):
            url = citation.get("url")
            title = citation.get("title")
        else:
            url = getattr(citation, "url", None)
            title = getattr(citation, "title", None)
        if url and not any(x.get("url") == url for x in out):
            out.append({"title": title or "", "url": url})
    return out[:12]


def response_urls(response):
    """Extract URL citations from a Responses API object without relying on SDK internals."""
    try:
        data = response.model_dump()
    except Exception:
        return []
    out = []

    def walk(value):
        if isinstance(value, dict):
            citation = value.get("url_citation")
            if isinstance(citation, dict) and citation.get("url"):
                url = citation.get("url")
                title = citation.get("title") or ""
                if not any(x.get("url") == url for x in out):
                    out.append({"title": title, "url": url})
            if value.get("type") == "url_citation" and value.get("url"):
                url = value.get("url")
                title = value.get("title") or ""
                if not any(x.get("url") == url for x in out):
                    out.append({"title": title, "url": url})
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return out[:12]


def search_story(client, story):
    source_hints = [
        {"publisher": s.get("publisher"), "title": s.get("title")}
        for s in (story.get("sources") or [])[:5]
    ]
    prompt = f"""
You are doing source research for ONE WORLD. ONE PEOPLE. Search the live web for
the news event below. Find the original or primary source where possible and at
least one independent source when available.

Do not decide whether the story is uplifting. Establish what actually happened.
Distinguish a completed/measured outcome from a launch, grant, pledge, award,
announcement, marketing claim or plan. Note if multiple articles appear to repeat
the same press release.

Candidate:
{json.dumps({
    "headline": story.get("headline_en"),
    "summary": story.get("summary_en"),
    "country": story.get("country"),
    "category": story.get("category"),
    "date": story.get("published_date"),
    "source_hints": source_hints,
}, ensure_ascii=False)}

Return a concise factual research note. Include concrete figures/dates only when
supported by sources. Do not invent missing facts.
""".strip()

    chat_error = ""
    try:
        completion = client.chat.completions.create(
            model=SEARCH_MODEL,
            web_search_options={"search_context_size": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        message = completion.choices[0].message
        return {
            "notes": message.content or "",
            "citations": annotation_urls(message),
            "backend": "chat_completions_search",
            "model": SEARCH_MODEL,
            "fallback_error": "",
        }
    except Exception as exc:
        chat_error = f"{type(exc).__name__}: {str(exc)[:220]}"

    # Fallback to the recommended Responses API web_search tool. A restricted key
    # must include api.responses.write for this branch to succeed.
    try:
        response = client.responses.create(
            model=RESPONSES_SEARCH_MODEL,
            tools=[{"type": "web_search", "search_context_size": "low"}],
            input=prompt,
        )
        return {
            "notes": response.output_text or "",
            "citations": response_urls(response),
            "backend": "responses_web_search",
            "model": RESPONSES_SEARCH_MODEL,
            "fallback_error": chat_error,
        }
    except Exception as exc:
        responses_error = f"{type(exc).__name__}: {str(exc)[:220]}"
        raise RuntimeError(f"chat search failed [{chat_error}]; responses search failed [{responses_error}]")


def verify_research(client, story, research):
    system = """You are the verification editor for ONE WORLD. ONE PEOPLE. (OWOP).
You receive an editorial candidate and a research note produced from live web
search with cited URLs.

Judge whether the concrete positive claim is supported. Be conservative.
A grant awarded, initiative launched, prize won, pledge made, programme announced
or campaign started is NOT evidence that the intended positive impact has happened.
Routine local human-interest stories may be factual but still too small for OWOP.
Prefer measurable outcomes, established improvements, scientific/medical advances,
restoration, meaningful community results, or significant human achievement.

Return ONLY valid JSON:
{
  "support":"supported|partially_supported|unsupported|unavailable",
  "outcome_status":"completed|measured_progress|announcement|unclear",
  "evidence_quality":"high|medium|low",
  "independence":"multiple_independent|likely_republication|single_source|unclear",
  "significance":"high|medium|low",
  "verified_headline":"neutral English headline, max 14 words",
  "verified_summary":"1-2 sentences containing only facts supported by the research",
  "verification_note":"max 45 words",
  "publish_recommendation":"publish|reserve|reject"
}

Use unavailable only when the search evidence is insufficient to judge. A story
can be factually supported yet still be reserve/reject because it lacks significance."""

    payload = {
        "candidate": {
            "id": story.get("id"),
            "headline": story.get("headline_en"),
            "summary": story.get("summary_en"),
            "why_good": story.get("why_good"),
            "category": story.get("category"),
            "country": story.get("country"),
            "editorial_score": story.get("score"),
            "editorial_significance": story.get("significance"),
            "editorial_outcome_status": story.get("outcome_status"),
        },
        "web_research": research,
    }

    response = client.chat.completions.create(
        model=VERIFY_MODEL,
        temperature=0,
        max_tokens=1000,
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
    candidates += [
        x for x in (editorial.get("reserves") or [])
        if int(x.get("score") or 0) >= 78 and str(x.get("significance") or "") == "high"
    ]
    candidates = candidates[:MAX_STORIES]

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        OUTPUT.write_text(json.dumps({
            "generated_at": generated,
            "ai_configured": False,
            "candidate_count": len(candidates),
            "stories": [],
            "message": "OPENAI_API_KEY unavailable",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    from openai import OpenAI
    client = OpenAI()
    results = []

    for story in candidates:
        try:
            research = search_story(client, story)
            assessment = verify_research(client, story, research)
            search_error = ""
        except Exception as exc:
            research = {"notes": "", "citations": [], "backend": "none", "model": "", "fallback_error": ""}
            assessment = {
                "support": "unavailable",
                "outcome_status": "unclear",
                "evidence_quality": "low",
                "independence": "unclear",
                "significance": "unclear",
                "verified_headline": story.get("headline_en") or "",
                "verified_summary": "",
                "verification_note": f"Verification pipeline failed: {type(exc).__name__}: {str(exc)[:140]}",
                "publish_recommendation": "reserve",
            }
            search_error = f"{type(exc).__name__}: {str(exc)[:180]}"

        results.append({
            "id": story.get("id"),
            "editorial_score": story.get("score"),
            "editorial_decision": story.get("decision"),
            "search_backend": research.get("backend") or "none",
            "search_model": research.get("model") or SEARCH_MODEL,
            "research_notes": research.get("notes") or "",
            "citations": research.get("citations") or [],
            "fallback_error": research.get("fallback_error") or "",
            "search_error": search_error,
            **assessment,
        })

    counts = {}
    for row in results:
        recommendation = row.get("publish_recommendation") or "unknown"
        counts[recommendation] = counts.get(recommendation, 0) + 1

    payload = {
        "generated_at": generated,
        "search_model": SEARCH_MODEL,
        "responses_search_model": RESPONSES_SEARCH_MODEL,
        "verify_model": VERIFY_MODEL,
        "ai_configured": True,
        "candidate_count": len(candidates),
        "recommendation_counts": counts,
        "stories": results,
        "pilot_note": "Live-web verification pilot; cited search evidence is re-evaluated by a separate verifier model.",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OWOP web verification: {len(results)} candidates; recommendations {counts}")


if __name__ == "__main__":
    main()
