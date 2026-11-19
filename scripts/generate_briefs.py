#!/usr/bin/env python3
"""Create source-grounded educational briefs; optional AI enrichment.

No API key: produces transparent, conservative structured briefs from official
source metadata and explicitly marks missing historical/outcome evidence.
With OPENAI_API_KEY: can enrich selected briefs using public source excerpts.
No identifiable patient data is sent to the AI API.
"""
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
FEED = DATA / "updates.json"
BRIEFS = DATA / "briefs.json"
STATUS = DATA / "brief_status.json"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
MAX_NEW = 12
MAX_BRIEFS = 100
MAX_AI = 5
UA = "HealthScope-Educational-Intelligence/1.0"

VOCAB = {
"Digital health": [
{"term":"Interoperability","meaning":"The ability of systems to exchange information and use it meaningfully."},
{"term":"Electronic health record (EHR)","meaning":"A digital longitudinal record of a person's health information."},
{"term":"Data quality","meaning":"Whether data is suitable, accurate and complete enough for a defined use."}],
"AI in healthcare": [
{"term":"Sensitivity","meaning":"The proportion of people with a condition correctly detected by a test or model."},
{"term":"Specificity","meaning":"The proportion of people without a condition correctly classified."},
{"term":"External validation","meaning":"Testing a model using data from settings separate from development."}],
"Public health": [
{"term":"Surveillance","meaning":"Continuous systematic collection and interpretation of health data for action."},
{"term":"Incidence","meaning":"New cases during a specified period in a defined population."},
{"term":"Denominator","meaning":"The defined population or total used to calculate a rate."}],
"Healthcare systems": [
{"term":"Coverage","meaning":"The proportion of an eligible population reached by a service."},
{"term":"Health information system (HIS)","meaning":"The people, policies, workflows and technologies used to produce health information."},
{"term":"Key performance indicator (KPI)","meaning":"A measurable indicator linked to a decision or operational objective."}],
"Clinical trials": [
{"term":"Study registration","meaning":"A public record describing a study protocol and status; not evidence that an intervention works."},
{"term":"Primary outcome","meaning":"The prespecified measure a study is mainly designed to assess."},
{"term":"Study population","meaning":"The participants eligible for inclusion under the protocol."}],
"Research & evidence": [
{"term":"Study design","meaning":"The methodological structure determining what conclusions a study can support."},
{"term":"Confidence interval","meaning":"An interval conveying uncertainty around a statistical estimate."},
{"term":"Confounding","meaning":"A factor associated with exposure and outcome that can distort an association."}]
}
METRICS = {
"Digital health":["Interoperability adoption = connected facilities / eligible facilities",
                  "Missing-record rate = required missing fields / required fields expected",
                  "Reporting timeliness = reports delivered on time / reports expected"],
"AI in healthcare":["Sensitivity and specificity on independent clinical datasets",
                     "Median review turnaround time for eligible cases",
                     "False-alert rate in the intended use population"],
"Public health":["Service coverage = reached eligible people / total eligible people",
                 "Reporting completeness = expected reports received / total reports expected",
                 "Disease case incidence per defined population and period"],
"Healthcare systems":["Service coverage by district and patient group",
                      "Stockout rate = facilities with a stockout / facilities reporting",
                      "Median referral or reporting turnaround time"],
"Clinical trials":["Primary outcome measure and prespecified time point",
                   "Enrollment versus target enrollment",
                   "Withdrawals and missing outcome data"],
"Research & evidence":["Absolute effect size and 95% confidence interval, if reported",
                       "Study sample size and selection criteria",
                       "Missing-data rate or risk of bias assessment"]
}
KEYWORDS = {"digital health": 5, "health information": 7, "health data": 8,
            "electronic health": 5, "interoperab": 9, "hospital": 2,
            "diagnostic": 2, "public health": 4, "health systems": 6,
            "surveillance": 5, "immuniz": 5, "vaccin": 4, "ai": 0,
            "clinical": 1, "informatics": 7, "data quality": 9,
            "health financing": 4, "digital": 4, "access to care": 4,
            "disease": 2, "implementation": 3}

def clean(value, maxlen=1800):
    text = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:maxlen]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as f:
        return json.loads(f.read())

def score(r):
    title = str(r.get("title") or "").lower()
    description = str(r.get("summary") or "").lower()
    s = sum(w for k,w in KEYWORDS.items() if k in title)
    s += sum(max(1,w//2) for k,w in KEYWORDS.items() if w and k in description)
    if r.get("source_type") == "Official announcement": s+=3
    if r.get("category") in ("Digital health","Healthcare systems","AI in healthcare"): s+=4
    if r.get("source_type") == "Clinical trial registry": s-=7
    if str(r.get("published",""))[:7] == NOW[:7]: s+=1
    return s

def extra_text(r):
    """Pull small public excerpts when possible, without retrieving private data."""
    url = str(r.get("url") or "")
    if "clinicaltrials.gov/study/" in url:
        nct = url.rstrip("/").rsplit("/",1)[-1]
        if not re.fullmatch(r"NCT\d{8}",nct):
            return ""
        try:
            study=fetch_json("https://clinicaltrials.gov/api/v2/studies/"+nct)
            p=study.get("protocolSection",{})
            d=p.get("descriptionModule",{})
            outcomes=p.get("outcomesModule",{}).get("primaryOutcomes",[])
            return clean("Brief summary: "+d.get("briefSummary","")+" Primary outcomes: "+
                "; ".join(x.get("measure","") for x in outcomes[:3]),3500)
        except (ValueError,urllib.error.URLError,TimeoutError):
            return ""
    if "pubmed.ncbi.nlm.nih.gov/" in url:
        match=re.search(r"/(\d+)/",url)
        if not match:
            return ""
        # PubMed EFetch gives abstract text, if available
        try:
            import xml.etree.ElementTree as ET
            q=urllib.parse.urlencode({"db":"pubmed","id":match.group(1),"retmode":"xml"})
            req=urllib.request.Request("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"+q,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=20) as f:root=ET.fromstring(f.read())
            paragraphs=[" ".join(t.itertext()) for t in root.findall(".//Abstract/AbstractText")]
            return clean(" ".join(paragraphs),3500)
        except (ValueError,urllib.error.URLError,TimeoutError,Exception):
            return ""
    return ""

def fallback(r):
    title=clean(r.get("title","An update"),240)
    src=clean(r.get("source","Original source"),120)
    description=clean(r.get("summary",""),900)
    typ=r.get("source_type","Source record")
    cat=r.get("category","Research & evidence")
    if cat not in VOCAB:cat="Research & evidence"
    is_trial=typ=="Clinical trial registry"
    is_paper=typ=="Research citation"
    intro=(src+" lists the following: “"+title+".” "+description)
    before="The available source metadata does not establish the exact prior workflow. To make a valid before-and-after comparison, review the publication and identify the setting, actors, existing processes and baseline metrics."
    change=("The record describes a registered or updated clinical study. Registration alone does not mean participants were treated or results were demonstrated." if is_trial else
            "The source identifies a research topic; verify the actual intervention and comparison group in the full paper before describing a change." if is_paper else
            "The publication or announcement is the documented development. The source metadata alone does not establish which clinical or operational workflows have already changed.")
    evidence=("A trial registration does not demonstrate improved healthcare outcomes. Check whether results are posted and assess the study design." if is_trial else
              "An indexed research citation is not enough to establish an effect. Read the methods, numerical results, and uncertainties in the primary paper." if is_paper else
              "No verified patient-level or system-level improvement can be inferred solely from this source listing. Seek independently measured before-and-after outcomes.")
    limitations="No independent causal evaluation has been performed for this auto-generated briefing. Do not infer effectiveness, national scale-up or improvements in mortality from announcements, metadata or registrations."
    return {"id":hashlib.sha256(str(r.get("url","")).encode()).hexdigest()[:20],
      "title":title,"source_title":title,"source":src,"published":str(r.get("published",""))[:10],
      "source_url":r.get("url",""),"evidence_type":typ,
      "evidence_status":"Evidence of improvement not established from feed metadata",
      "mode":"Automatic source-based outline (not a verified impact study)",
      "generated_at":NOW[:10],"what_happened":intro,
      "before":before,"what_changed":change,"evidence":evidence,
      "limitations":limitations,"vocabulary":VOCAB[cat],"metrics":METRICS[cat],
      "bi_lessons":"Define the unit of analysis, baseline and denominator before interpreting this development. Propose KPIs relevant to the intervention and verify whether observed changes can be attributed to it.",
      "question":"What primary-source evidence would allow us to distinguish a promising announcement from a measurable improvement in healthcare delivery?",
      "review_note":"Automatically generated from source metadata. Read the original publication before treating any specific claim as established."}

def ai_brief(r,base,context):
    api_key=os.environ.get("OPENAI_API_KEY","").strip()
    if not api_key:return None
    model=os.environ.get("HEALTHSCOPE_AI_MODEL","gpt-4.1-mini")
    prompt={
      "task":"Produce a concise educational healthcare intelligence briefing using ONLY the source material provided. Separate facts from proposed BI metrics.",
      "rules":[
        "Treat the supplied excerpt as the only factual source. Never infer missing historical process, implementation, outcomes, numbers or patient benefit.",
        "If a detail is not explicitly supported, say 'Not established by the available source'.",
        "A clinical trial registration is not proof that a treatment works. Avoid causal claims without valid outcome evidence.",
        "Use accessible professional English, clearly explain essential vocabulary.",
        "Include no patient-level medical advice. Avoid promotional or hype language.",
        "Do not claim independent verification; the content is generated and must be checked against the original publication.",
        "Output a JSON object with precisely these keys: what_happened, before, what_changed, evidence, limitations, bi_lessons, question, vocabulary, metrics.",
        "vocabulary is an array of up to 3 objects with term and meaning strings. metrics is an array of up to 3 suggested KPI strings.",
      ],
      "record":{"title":r.get("title"),"date":r.get("published"),"source":r.get("source"),
        "type":r.get("source_type"),"link":r.get("url"),"source_summary":r.get("summary"),
        "additional_source_excerpt":context}
    }
    request_body={"model":model,
      "input":[{"role":"system","content":[{"type":"input_text","text":"You are a careful healthcare evidence communicator. Produce JSON only. Never invent source-supported outcomes."}]},
               {"role":"user","content":[{"type":"input_text","text":json.dumps(prompt,ensure_ascii=False)}]}],
      "text":{"format":{"type":"json_object"}}}
    req=urllib.request.Request("https://api.openai.com/v1/responses",
      data=json.dumps(request_body).encode("utf-8"),
      headers={"Content-Type":"application/json","Authorization":"Bearer "+api_key,"User-Agent":UA},
      method="POST")
    with urllib.request.urlopen(req,timeout=65) as resp:
        response=json.load(resp)
    message="".join(part.get("text","") for item in response.get("output",[])
      for part in item.get("content",[]) if part.get("type")=="output_text")
    parsed=json.loads(message)
    required=["what_happened","before","what_changed","evidence","limitations","bi_lessons","question"]
    if not all(isinstance(parsed.get(k),str) and parsed[k].strip() for k in required):
        raise ValueError("Incomplete explanation returned")
    out=base.copy()
    for key in required:out[key]=clean(parsed[key],1200)
    if isinstance(parsed.get("vocabulary"),list):
        words=[{"term":clean(v.get("term"),80),"meaning":clean(v.get("meaning"),250)}
          for v in parsed["vocabulary"][:3] if isinstance(v,dict)]
        if words:out["vocabulary"]=words
    if isinstance(parsed.get("metrics"),list):
        vals=[clean(m,220) for m in parsed["metrics"][:3] if isinstance(m,str)]
        if vals:out["metrics"]=vals
    out["mode"]="AI-assisted source-based explanation (unreviewed)"
    out["evidence_status"]="AI synthesis — verify numerical and outcome claims against the original source"
    out["review_note"]="AI-assisted educational summary grounded in supplied source excerpts; not independently verified. Read the original publication for full evidence."
    return out

def main():
    feed=json.loads(FEED.read_text(encoding="utf-8"))
    previous=json.loads(BRIEFS.read_text(encoding="utf-8")) if BRIEFS.exists() else []
    old={b["source_url"]:b for b in previous if isinstance(b,dict) and b.get("source_url")}
    ordered=sorted([r for r in feed if isinstance(r,dict) and str(r.get("url","")).startswith("https://")],
       key=lambda r:(score(r),r.get("published","")),reverse=True)
    selected=[r for r in ordered if score(r)>=4 and r["url"] not in old][:MAX_NEW]
    ai_count=0
    statuses=[]
    for r in selected:
        brief=fallback(r)
        if os.environ.get("OPENAI_API_KEY") and ai_count<MAX_AI:
            try:
                excerpt=extra_text(r)
                # For announcements, the RSS summary may only be one or two sentences.
                # Do not pretend this constitutes a comprehensive source review.
                brief=ai_brief(r,brief,excerpt) or brief
                ai_count+=1
                statuses.append({"url":r["url"],"status":"ai_assisted"})
            except Exception as e:
                statuses.append({"url":r["url"],"status":"fallback","reason":type(e).__name__})
        old[r["url"]]=brief
    briefs=list(old.values())
    briefs.sort(key=lambda b:(b.get("mode","").startswith("Editorially"),b.get("published","")),reverse=True)
    BRIEFS.write_text(json.dumps(briefs[:MAX_BRIEFS],indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    STATUS.write_text(json.dumps({"last_generated":NOW,"available_briefs":len(briefs[:MAX_BRIEFS]),
        "new_briefs":len(selected),"ai_enriched":ai_count,
        "ai_enabled":bool(os.environ.get("OPENAI_API_KEY")),"items":statuses,
        "limitations":"Automatic briefs may lack full source context; AI outputs are unreviewed and must be checked."},indent=2)+"\n",encoding="utf-8")
    print("Briefs written:",len(briefs[:MAX_BRIEFS]),"new:",len(selected),"AI enriched:",ai_count)

if __name__=="__main__":
    main()
