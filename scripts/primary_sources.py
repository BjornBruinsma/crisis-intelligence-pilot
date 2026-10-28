#!/usr/bin/env python3
"""Fetch *actual official-source publications* to support the research pilot.

Only trusted government domains, not Google search result links. We retain
short passages and URLs, never claim they verify a third-party headline.
Errors are recorded. Pages may change and content may be unavailable.
"""
import datetime as dt
import email.utils
import html
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"site"/"data"
ROOT.mkdir(parents=True,exist_ok=True)
OUTPUT=ROOT/"primary_sources.json"
SOURCES=[
 ("centcom_releases","US Central Command",
  "https://www.centcom.mil/MEDIA/PUBLIC-RELEASES/","official_listing"),
 ("uk_iran","UK Foreign, Commonwealth & Development Office",
  "https://www.gov.uk/foreign-travel-advice/iran","official_advisory"),
 ("uk_saudi","UK Foreign, Commonwealth & Development Office",
  "https://www.gov.uk/foreign-travel-advice/saudi-arabia","official_advisory"),
 ("us_advisories","US Department of State",
  "https://travel.state.gov/_res/rss/TAsTWs.xml","official_rss")
]
TRUSTED_HOSTS={"www.centcom.mil","centcom.mil","www.gov.uk","gov.uk",
               "travel.state.gov"}
KEYWORDS=("iran","saudi","israel","gulf","kuwait","bahrain","qatar",
          "hormuz","iraq","united arab emirates","united states",
          "middle east","evacuat","strike","military","warning","embassy",
          "blockade","travel","risk","tanker","attack","war","security",
          "shipping","airspace","houthis","yemen","withdraw","closed")

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def valid_official_url(url):
    try:
        u=urllib.parse.urlsplit(str(url))
        return u.scheme=="https" and (u.hostname or "").lower() in TRUSTED_HOSTS
    except ValueError:
        return False

class Extract(HTMLParser):
    def __init__(self,root_url):
        super().__init__(convert_charrefs=True)
        self.root=root_url
        self.stack=[]
        self.skip=0
        self.current=[]
        self.chunks=[]
        self.links=[]
        self.anchor=None
    def handle_starttag(self,tag,attrs):
        attr=dict(attrs)
        if tag in {"script","style","svg","noscript"}:
            self.skip+=1
        self.stack.append(tag)
        if tag=="a" and self.skip==0:
            self.anchor=(attr.get("href") or "",[])
        if tag in {"p","h1","h2","h3","li"} and self.skip==0:
            self.current.append((tag,[]))
    def handle_data(self,data):
        if self.skip:return
        if self.anchor:self.anchor[1].append(data)
        for _,part in self.current:
            part.append(data)
    def handle_endtag(self,tag):
        if tag in {"script","style","svg","noscript"} and self.skip:
            self.skip-=1
        if tag=="a" and self.anchor:
            link,text=self.anchor
            url=urllib.parse.urljoin(self.root,link)
            label=re.sub(r"\s+"," ","".join(text)).strip()
            if valid_official_url(url) and len(label)>18:
                self.links.append({"title":label[:200],"url":url})
            self.anchor=None
        if tag in {"p","h1","h2","h3","li"} and self.current:
            for i in range(len(self.current)-1,-1,-1):
                if self.current[i][0]==tag:
                    _,part=self.current.pop(i)
                    value=re.sub(r"\s+"," ","".join(part)).strip()
                    if 28<=len(value)<=1800 and value not in self.chunks:
                        self.chunks.append(value[:800])
                    break
        if self.stack:
            if self.stack[-1]==tag:self.stack.pop()
            elif tag in self.stack:self.stack=self.stack[:self.stack.index(tag)]

def relevant(text):
    t=str(text or "").lower()
    return any(k in t for k in KEYWORDS)

def fetch(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"CRISIS-Intelligence-Research/0.5",
        "Accept":"application/rss+xml, application/xml, text/html, */*"})
    with urllib.request.urlopen(req,timeout=22) as response:
        return response.read(1_800_000)

def parse_document(item,raw):
    doc={"id":item[0],"authority":item[1],"url":item[2],
         "kind":item[3],"retrieved_at":now(),"status":"ok","title":item[1],
         "passages":[],"links":[]}
    if item[3]=="official_rss":
        root=ET.fromstring(raw)
        for entry in root.findall(".//item")[:60]:
            def val(t):
                e=entry.find(t)
                return (e.text or "").strip() if e is not None else ""
            title=val("title")
            link=val("link")
            desc=re.sub(r"<[^>]*>"," ",html.unescape(val("description")))
            if relevant(title+" "+desc) and valid_official_url(link):
                doc["links"].append({"title":title[:230],"url":link,
                                     "published":val("pubDate")[:60],
                                     "excerpt":re.sub(r"\s+"," ",desc).strip()[:400]})
        doc["title"]="US travel advice RSS (filtered: Middle East)"
        return doc
    parser=Extract(item[2])
    parser.feed(raw.decode("utf-8",errors="replace"))
    matches=[x for x in parser.chunks if relevant(x)]
    doc["passages"]=matches[:40]
    matches_links=[x for x in parser.links if relevant(x["title"])]
    seen=set()
    for x in matches_links:
        if x["url"] in seen:continue
        seen.add(x["url"])
        doc["links"].append(x)
        if len(doc["links"])>=30:break
    return doc

def collect():
    docs=[];errors={}
    for item in SOURCES:
        try:
            doc=parse_document(item,fetch(item[2]))
            # Even an HTML response may be an error/login page; don't call it successful evidence.
            if not doc["passages"] and not doc["links"]:
                doc["status"]="empty"
            docs.append(doc)
        except Exception as exc:
            err=f"{type(exc).__name__}: {str(exc)[:150]}"
            errors[item[0]]=err
            docs.append({"id":item[0],"authority":item[1],"url":item[2],
                         "kind":item[3],"retrieved_at":now(),"status":"error",
                         "error":err,"passages":[],"links":[]})
    return {"last_attempt_utc":now(),
            "description":"Official-source texts and links, not automatic verification of events",
            "sources":docs,"errors":errors}

def main():
    report=collect()
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Primary sources: "+", ".join(f"{d['id']}={d['status']} "
          f"({len(d['passages'])} passages/{len(d['links'])} links)" for d in report["sources"]))
if __name__=="__main__":main()
