#!/usr/bin/env python3
"""Public GDELT DOC article candidates, not verified events or war probabilities."""
import datetime as dt, json, re, time, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"site"/"data"
ROOT.mkdir(parents=True,exist_ok=True)
QUERIES={
"Militair & veiligheid":"(Iran OR Hormuz) (military OR missiles OR airstrikes OR drones OR attack)",
"Politiek & diplomatie":"Iran (diplomacy OR negotiations OR ceasefire OR sanctions OR talks)",
"Overheden & crisismaatregelen":"(Iran OR Saudi) (evacuation OR embassy OR travel advisory OR emergency)",
"Financiële markten":"(Iran OR Hormuz) (oil futures OR insurance OR bonds OR stocks OR currency)",
"Energie & grondstoffen":"(Iran OR Hormuz) (diesel OR LNG OR refinery OR pipeline OR oil)",
"Wereldhandel & logistiek":"(Iran OR Hormuz) (shipping OR tanker OR freight OR airline OR supply chain)",
"Bedrijfsleven & investeringen":"(Iran OR Gulf) (companies OR investment OR employees OR operations OR business)",
"Economie & samenleving":"(Iran OR Hormuz) (inflation OR fuel shortages OR food prices OR tourism OR economy)"}

def read(path,default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError): return default

def fetch(query):
    params=urllib.parse.urlencode(dict(query=query,mode="artlist",format="json",sort="datedesc",maxrecords=50,timespan="12h"))
    url="https://api.gdeltproject.org/api/v2/doc/doc?"+params
    err=""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"CRISIS-Intelligence-Pilot/0.2"}),timeout=30) as resp:
                obj=json.loads(resp.read(4000000))
            return obj.get("articles",[]),None
        except Exception as exc:
            err=str(exc)[:180]
            if attempt<2: time.sleep(2*(attempt+1))
    return [],err

def seen(s):
    s=str(s or "")
    if re.fullmatch(r"\\d{8}T\\d{6}Z?",s):
        return s[:4]+"-"+s[4:6]+"-"+s[6:8]+"T"+s[9:11]+":"+s[11:13]+":"+s[13:15]+"Z"
    return s

def main():
    now=dt.datetime.now(dt.timezone.utc)
    article_file=ROOT/"articles.json"
    before=read(article_file,{"articles":[]}).get("articles",[])
    by_url={x["url"]:x for x in before if isinstance(x,dict) and x.get("url")}
    errors={}; added=0; success=0
    for category,query in QUERIES.items():
        records,error=fetch(query)
        if error:
            errors[category]=error
            continue
        success+=1
        for item in records:
            url=str(item.get("url",""))
            if not url.startswith(("https://","http://")): continue
            if url not in by_url:
                added+=1
                by_url[url]=dict(url=url,title=str(item.get("title") or "Zonder titel")[:350],first_seen=seen(item.get("seendate")),language=item.get("language",""),domain=item.get("domain",""),sourcecountry=item.get("sourcecountry",""),topic=[category],review_status="unverified")
            elif category not in by_url[url].setdefault("topic",[]):
                by_url[url]["topic"].append(category)
        time.sleep(1)
    cutoff=now-dt.timedelta(days=31)
    def is_recent(x):
        try:
            return dt.datetime.fromisoformat(x.get("first_seen","").replace("Z","+00:00"))>=cutoff
        except (ValueError,TypeError): return True
    saved=sorted((x for x in by_url.values() if is_recent(x)),key=lambda x:x.get("first_seen",""),reverse=True)[:12000]
    if success:
        article_file.write_text(json.dumps(dict(source="GDELT DOC 2.0 ArticleList",description="Unverified candidate news articles, not confirmed incidents",last_success_utc=now.isoformat(),articles=saved),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"fetch_status.json").write_text(json.dumps(dict(last_attempt_utc=now.isoformat(),status="ok" if success==len(QUERIES) else ("partial" if success else "error"),queries_ok=success,queries_total=len(QUERIES),new_urls=added,retained_urls=len(saved),errors=errors),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"GDELT {success}/{len(QUERIES)} success, {added} new URLs")

if __name__=="__main__": main()
