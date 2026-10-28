#!/usr/bin/env python3
"""Cluster OWOP candidates and let an AI editorial board decide what to publish.

Pilot philosophy: AI-first, no human queue. Three roles independently score the
same candidate set; a final editor combines their judgements and writes short
original summaries. If OPENAI_API_KEY is absent, the script exits successfully
and records that AI review is awaiting configuration.
"""
import collections
import datetime as dt
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "site" / "owop"
DATA = ROOT / "data"
MODEL = os.getenv("OWOP_MODEL", "gpt-4o-mini")
MAX_ARTICLES = 700
MAX_GROUPS = 80
PUBLISH_THRESHOLD = 75
RESERVE_THRESHOLD = 60

LOW_SIGNAL = [
    "celebrity", "horoscope", "lottery", "giveaway", "sale", "discount", "coupon",
    "match preview", "transfer rumor", "box office", "red carpet", "royal family",
]


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def normalized(title):
    title = unicodedata.normalize("NFKC", str(title or "")).casefold()
    title = re.sub(r"\s+[-–—]\s+[^-–—]{1,90}$", "", title)
    title = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", title, flags=re.UNICODE).strip()


def tokens(title):
    return {w for w in normalized(title).split() if len(w) >= 3}


def sim(a, b):
    aa, bb = tokens(a), tokens(b)
    if min(len(aa), len(bb)) < 4:
        return 1.0 if normalized(a) == normalized(b) else 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def cluster_articles(articles):
    groups = []
    by_day = collections.defaultdict(list)
    for row in articles:
        title = str(row.get("title") or "").strip()
        if not title or any(x in title.casefold() for x in LOW_SIGNAL):
            continue
        day = str(row.get("published_at") or row.get("first_seen") or "")[:10]
        group = None
        for idx in by_day[day]:
            if sim(groups[idx]["title"], title) >= 0.72:
                group = groups[idx]
                break
        if group is None:
            group = {"title": title, "day": day, "articles": []}
            by_day[day].append(len(groups))
            groups.append(group)
        group["articles"].append(row)
    for g in groups:
        pubs = sorted({str(a.get("publisher") or a.get("domain") or "unknown") for a in g["articles"]})
        g["source_count"] = len(pubs)
        g["publishers"] = pubs
        g["topics"] = sorted({str(t) for a in g["articles"] for t in (a.get("topic") or [])})
        g["key"] = hashlib.sha256((g["day"] + ":" + normalized(g["title"])).encode()).hexdigest()[:14]
        g["urls"] = [a.get("url") for a in g["articles"][:6] if a.get("url")]
        g["languages"] = sorted({str(a.get("language") or "") for a in g["articles"] if a.get("language")})
        g["countries"] = sorted({str(a.get("sourcecountry") or "") for a in g["articles"] if a.get("sourcecountry")})
        g["pre_rank"] = min(4, g["source_count"]) + min(2, len(g["topics"]))
    groups.sort(key=lambda g: (g["day"], g["pre_rank"], g["source_count"]), reverse=True)
    return groups


def compact_groups(groups):
    out = []
    for g in groups:
        out.append({
            "id": g["key"], "date": g["day"], "headline": g["title"],
            "sources": g["publishers"][:5], "source_count": g["source_count"],
            "topics": g["topics"][:4], "languages": g["languages"][:4],
            "countries": g["countries"][:4],
        })
    return out


def parse_json_text(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    return json.loads(text)


def ask(client, instruction, candidates):
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": "CANDIDATES:\n" + json.dumps(candidates, ensure_ascii=False)},
        ],
    )
    return parse_json_text(response.choices[0].message.content or "")


def role_prompts():
    common = """
You are evaluating candidate headlines for ONE WORLD. ONE PEOPLE. (OWOP), a non-political global news feed about real, verifiable positive developments. This is NOT a feel-good fluff site. A story should show something measurably improved, restored, solved, protected, discovered, opened, recovered, reduced, made safer, or people concretely helping others. Plans, promises, PR, vague optimism, celebrity fluff and ordinary commercial launches should score low. Do not treat governments or countries as good/bad. Judge the event, not ideology. Headlines may be in any language; understand/translate them. You only have metadata/headlines in this pilot, so penalize unverifiable certainty. Return ONLY valid JSON with shape {"reviews":[{"id":"...","score":0-100,"reason":"max 20 words"}]}. Include every candidate exactly once.
"""
    return {
        "good_news": common + "\nROLE: Good News Editor. Focus on whether a genuinely positive, interesting development appears to have happened.",
        "skeptic": common + "\nROLE: Sceptic / Fact Checker. Be strict about PR, unsupported superlatives, plans vs completed results, and misleading framing.",
        "owop": common + "\nROLE: OWOP Editor. Focus on cross-cultural human relevance, solutions, nature, health, science, community and meaningful progress.",
    }


def by_id(review_payload):
    return {str(x.get("id")): x for x in review_payload.get("reviews", []) if isinstance(x, dict) and x.get("id")}


def final_decision_prompt(candidates, role_reviews):
    combined = []
    role_maps = {k: by_id(v) for k, v in role_reviews.items()}
    for c in candidates:
        item = dict(c)
        item["panel"] = {name: role_maps[name].get(c["id"], {}) for name in role_maps}
        combined.append(item)
    instruction = """
You are the final editor of ONE WORLD. ONE PEOPLE. Use the three panel reviews plus the headline metadata. Decide conservatively. Publish only if the development seems genuinely positive AND sufficiently plausible from the available metadata. Reserve uncertain but promising stories. Reject fluff, PR, mere plans, partisan/political messaging, tragedy-with-a-tiny-positive-angle, or stories whose positive meaning is unclear.

Return ONLY valid JSON with shape:
{"decisions":[{
  "id":"...", "score":0-100, "decision":"publish|reserve|reject",
  "category":"Nature|Health|Science|People|Community|Climate & Energy|Progress|Other",
  "country":"country/region if inferable, else Global",
  "headline_en":"neutral English headline, max 14 words",
  "summary_en":"original 1-2 sentence summary based ONLY on what the metadata supports; never invent facts",
  "why_good":"one short sentence explaining the positive development",
  "confidence":"high|medium|low",
  "editor_note":"max 25 words"
}]}
Include every candidate exactly once. The score is editorial confidence/fit, not moral worth.
"""
    return instruction, combined


def main():
    feed = load(DATA / "articles.json", {"articles": []})
    articles = list(feed.get("articles") or [])[:MAX_ARTICLES]
    groups = cluster_articles(articles)[:MAX_GROUPS]
    candidates = compact_groups(groups)
    generated = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    if not os.getenv("OPENAI_API_KEY"):
        status = {
            "generated_at": generated, "model": MODEL, "ai_configured": False,
            "candidate_groups": len(candidates), "message": "Set OPENAI_API_KEY GitHub secret to enable AI editorial review.",
            "stories": [], "reserves": [], "rejected": [],
        }
        (DATA / "editorial.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(status["message"])
        return

    from openai import OpenAI
    client = OpenAI()
    reviews = {}
    for name, prompt in role_prompts().items():
        reviews[name] = ask(client, prompt, candidates)

    instruction, combined = final_decision_prompt(candidates, reviews)
    final = ask(client, instruction, combined)
    decisions = {str(x.get("id")): x for x in final.get("decisions", []) if isinstance(x, dict)}
    group_map = {g["key"]: g for g in groups}

    stories, reserves, rejected = [], [], []
    for cid, decision in decisions.items():
        g = group_map.get(cid)
        if not g:
            continue
        obj = dict(decision)
        obj["source_count"] = g["source_count"]
        obj["sources"] = [
            {"publisher": a.get("publisher") or a.get("domain") or "Source", "url": a.get("url"), "title": a.get("title")}
            for a in g["articles"][:6]
        ]
        obj["published_date"] = g["day"]
        score = int(obj.get("score") or 0)
        wanted = str(obj.get("decision") or "reject")
        if wanted == "publish" and score >= PUBLISH_THRESHOLD:
            stories.append(obj)
        elif score >= RESERVE_THRESHOLD and wanted != "reject":
            obj["decision"] = "reserve"
            reserves.append(obj)
        else:
            obj["decision"] = "reject"
            rejected.append(obj)

    stories.sort(key=lambda x: (int(x.get("score") or 0), x.get("published_date") or ""), reverse=True)
    reserves.sort(key=lambda x: int(x.get("score") or 0), reverse=True)
    payload = {
        "generated_at": generated, "model": MODEL, "ai_configured": True,
        "candidate_groups": len(candidates), "published_count": len(stories),
        "reserve_count": len(reserves), "rejected_count": len(rejected),
        "stories": stories, "reserves": reserves, "rejected": rejected,
        "panel_reviews": reviews,
        "pilot_note": "AI-only editorial pilot; headline/metadata review, not yet full-article verification.",
    }
    (DATA / "editorial.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OWOP AI: {len(stories)} publish, {len(reserves)} reserve, {len(rejected)} reject")


if __name__ == "__main__":
    main()
