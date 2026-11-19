"""Read original public evidence before writing a HealthScope analysis.

This is NOT a general web crawler. Only approved primary-source hosts can be fetched.
Source text is transient for analysis and is not archived in the public repository.
"""
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import json
import re
import xml.etree.ElementTree as ET

USER_AGENT = "HealthScope-LearningResearch/1.1 (public-source-reader)"
ALLOWED = {"who.int", "afro.who.int", "www.who.int",
           "pubmed.ncbi.nlm.nih.gov", "clinicaltrials.gov", "www.clinicaltrials.gov"}
LIMIT = 10500

def normalize(text, limit=LIMIT):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]

def request(url, accept="text/html"):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED:
        raise ValueError("Unsupported original-source host")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(req, timeout=18) as response:
        final = urlparse(response.url)
        if final.scheme != "https" or final.hostname not in ALLOWED:
            raise ValueError("Unexpected source redirect")
        body = response.read(300_000)
    return body

class ArticleText(HTMLParser):
    """Extract article or main text while excluding menus and scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.skip_depth = 0
        self.depth_main = 0
        self.depth_article = 0
        self.main = []
        self.article = []
        self.body = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
        if tag in {"script","style","svg","nav","footer","header","noscript"}:
            self.skip_depth += 1
        if tag == "main": self.depth_main += 1
        if tag == "article": self.depth_article += 1
        if tag in {"p","h1","h2","h3","li","section"}:
            self.handle_data(" ")

    def handle_endtag(self, tag):
        if tag == "main" and self.depth_main: self.depth_main -= 1
        if tag == "article" and self.depth_article: self.depth_article -= 1
        if tag in {"script","style","svg","nav","footer","header","noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.stack:
            while self.stack:
                removed = self.stack.pop()
                if removed == tag: break
        if tag in {"p","div","h1","h2","h3","li"}: self.handle_data(" ")

    def handle_data(self, data):
        if not self.skip_depth:
            if self.depth_article: self.article.append(data)
            if self.depth_main: self.main.append(data)
            self.body.append(data)

    def best(self):
        for candidate in (self.article,self.main,self.body):
            candidate = normalize(" ".join(candidate))
            if len(candidate) > 450:
                return candidate
        return ""

def pubmed_original(url):
    m = re.search(r"/(\d+)/?",url)
    if not m: return None
    pmid = m.group(1)
    q = urlencode({"db":"pubmed","id":pmid,"retmode":"xml"})
    host = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
    req = Request(host + q, headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=18) as f:
        tree = ET.fromstring(f.read(300_000))
    paragraphs=[]
    for element in tree.findall(".//Abstract/AbstractText"):
        prefix=element.attrib.get("Label","")
        paragraphs.append(normalize(prefix+": "+"".join(element.itertext()),2500))
    text=normalize(" ".join(paragraphs),LIMIT)
    publication_types=[normalize("".join(x.itertext()),130)
        for x in tree.findall(".//PublicationTypeList/PublicationType")][:5]
    return {"method":"PubMed abstract via NCBI EFetch","text":text,
            "study_type":", ".join(publication_types) or "Not specified",
            "results_available":bool(text)}

def registry_original(url):
    match=re.search(r"/study/(NCT\d{8})",url)
    if not match:return None
    api="https://clinicaltrials.gov/api/v2/studies/"+match.group(1)
    with urlopen(Request(api,headers={"User-Agent":USER_AGENT,"Accept":"application/json"}),timeout=18) as f:
        record=json.loads(f.read(300_000))
    p=record.get("protocolSection",{})
    status=p.get("statusModule",{})
    design=p.get("designModule",{})
    description=p.get("descriptionModule",{})
    outcome=p.get("outcomesModule",{})
    arms=p.get("armsInterventionsModule",{})
    results=record.get("resultsSection",{})
    parts=[
      "Registration: "+match.group(1),
      "Recruitment status: "+status.get("overallStatus","not stated"),
      "Study type: "+design.get("studyType","not stated"),
      "Target enrollment: "+str(design.get("enrollmentInfo",{}).get("count","not stated")),
      "Brief description: "+description.get("briefSummary",""),
      "Detailed description: "+description.get("detailedDescription",""),
      "Interventions: "+"; ".join(x.get("name","") for x in arms.get("interventions",[])[:7]),
      "Primary outcomes: "+"; ".join((x.get("measure","")+" — "+x.get("timeFrame","")) for x in outcome.get("primaryOutcomes",[])[:5]),
      "Posted results: "+("yes" if results else "no")
    ]
    return {"method":"ClinicalTrials.gov protocol and results sections",
            "text":normalize(" ".join(parts),LIMIT),
            "study_type":design.get("studyType","Clinical study"),
            "results_available":bool(results)}

def who_original(url):
    body=request(url)
    reader=ArticleText()
    reader.feed(body.decode("utf-8","replace"))
    return {"method":"WHO original public HTML article",
            "text":reader.best(),"study_type":"Institutional announcement",
            "results_available":False}

def source_packet(record):
    url=str(record.get("url",""))
    fetched=datetime.now(timezone.utc).isoformat(timespec="seconds")
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in ALLOWED:
        return {"source_url":url,"source_title":record.get("title",""),
                "retrieved_at":fetched,"method":"Unsupported host","text":"",
                "study_type":"","results_available":False,
                "source_level":"Metadata only","reason":"Host is not allowlisted"}
    try:
        if "pubmed.ncbi.nlm.nih.gov" in parsed.hostname:
            data=pubmed_original(url)
        elif "clinicaltrials.gov" in parsed.hostname:
            data=registry_original(url)
        elif "who.int" in parsed.hostname:
            data=who_original(url)
        else:
            data=None
        data=data or {}
        text=data.get("text","")
        level="Primary source excerpt" if len(text)>=450 else "Metadata only"
        return {"source_url":url,"source_title":record.get("title",""),
                "retrieved_at":fetched,"method":data.get("method","Original record unavailable"),
                "text":text,"study_type":data.get("study_type",""),
                "results_available":data.get("results_available",False),
                "source_level":level,"reason":"" if len(text)>=450 else "Insufficient source text"}
    except Exception as exc:
        return {"source_url":url,"source_title":record.get("title",""),
                "retrieved_at":fetched,"method":"Original source retrieval failed",
                "text":"","study_type":"","results_available":False,
                "source_level":"Metadata only","reason":type(exc).__name__}

def short_public_provenance(packet):
    """Only metadata is persisted; do not republish copyrighted article text."""
    return {"title":packet.get("source_title","Original source"),
            "url":packet.get("source_url",""),
            "type":packet.get("study_type",""),
            "method":packet.get("method",""),
            "retrieved_at":packet.get("retrieved_at",""),
            "source_level":packet.get("source_level",""),
            "reason":packet.get("reason","")}
