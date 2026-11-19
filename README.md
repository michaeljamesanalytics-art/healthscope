# HealthScope — Global Healthcare Intelligence & Learning Hub

A source-linked healthcare learning application built for a developing healthcare data analyst and business intelligence developer.

**Current status:** Initial web application and daily public-source collector committed to GitHub. GitHub Pages still needs to be enabled in repository settings. The scheduled data ingestion has not yet been tested through an Actions run. Optional email requires SMTP secrets.

## Features

- Responsive browser-based dashboard and global healthcare reading feed
- Searchable dictionary of 30 healthcare, epidemiology, quality and BI terms
- Specific before/after country examples: Rwanda, Kenya, Bauchi State in Nigeria and South Africa
- Synthetic clinic analytics lab, KPI comparison and CSV export
- Four-week learning roadmap with progress stored locally in the browser
- Evidence-aware **Intelligence Briefs**: what happened, previous process, what changed, documented impact, unknowns, vocabulary and analyst KPIs
- Daily automatic brief outlines from source metadata, with an optional AI-assisted explanation mode
- Saved readings stored locally in the browser
- Automated metadata intake from WHO RSS, PubMed E-utilities and ClinicalTrials.gov

## Publishing on GitHub Pages

1. Open **Settings → Pages** in this repository.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select **main** and **/docs**, then Save.
4. Once deployed, the intended public URL is:
   **https://michaeljamesanalytics-art.github.io/healthscope/**
5. If it is not live yet, check the Pages deployment result in the Actions tab.

## Update feed

The workflow at `.github/workflows/daily-healthscope.yml` is configured for 06:00 UTC (07:00 WAT) each day, subject to GitHub's schedule delays.

Start a manual run at **Actions → Update HealthScope daily → Run workflow**. The collector is standard-library Python and can also run locally with:

```bash
python scripts/update_feed.py
```

After source collection, the workflow runs `scripts/generate_briefs.py`. It selects healthcare-relevant records, preserves previously prepared briefs, and creates conservative, clearly labeled explanations in `docs/data/briefs.json`. When evidence of a previous process or measurable improvement is unavailable, the brief says so rather than inventing an answer. The daily run processes up to 12 new records and retains up to 100 briefs.

It saves public source metadata in `docs/data/updates.json` and source status in `docs/data/status.json`. It does not scrape full news articles or store patient data. Individual source failures are recorded without discarding the existing feed.

If the workflow cannot commit its data, check **Settings → Actions → General → Workflow permissions** to ensure the GitHub Actions token can write repository contents.

## How a HealthScope research dossier is prepared

1. Select recent, relevant healthcare developments rather than every headline.
2. Retrieve original source material: WHO public articles, PubMed abstracts via NCBI EFetch, or ClinicalTrials.gov protocol and results records.
3. Explicitly distinguish an announcement, research finding, study registration and measured improvement.
4. Teach the old workflow, what changed, the evidence, professional vocabulary and an applied healthcare BI/SQL exercise.
5. Show the primary-source link, retrieval depth, and any short quotations verified against the fetched source text.
6. Require a human review before external publication of clinical effectiveness or system impact claims.

Carefully prepared teaching cases live in docs/data/editorial_briefs.json and are retained across daily feed updates.

IMPORTANT: A single WHO news item or PubMed abstract cannot substitute for a full multi-source literature review. Full texts may be inaccessible; separate reports can be needed to establish the previous workflow and demonstrated outcomes. The app labels missing evidence instead of inventing it.
## Optional AI-enhanced briefs

**The app works without an AI subscription or key.** By default, new briefs are structured, source-linked learning outlines based on limited feed metadata. They explain the news at a high level, but they cannot establish previous workflows or measured improvements without supporting evidence.

For more detailed AI-assisted explanations, create a paid OpenAI API key and add it as a GitHub Actions **repository secret** named `OPENAI_API_KEY`. Do not place the key in browser code or commit it to GitHub. The workflow defaults to model `gpt-4.1-mini` and limits processing to 3 newly selected briefs per daily run. API usage is billed separately by the provider; monitor usage and set a budget. A source excerpt may be sent to the API, but never identifiable patient data.

**Important:** AI-enhanced briefs are *unreviewed educational summaries*, not independently validated healthcare evidence. They must contain a short quote that matches the retrieved source text exactly, or the app retains a conservative reading note. The source record may not contain enough facts to make a meaningful before-versus-after comparison, and the app will acknowledge that limitation. Review original sources before citing or making decisions. The generation status is saved in `docs/data/brief_status.json` after the run.

## Optional daily email

In **Settings → Secrets and variables → Actions**, add these repository secrets if you want email notifications:

- `SMTP_HOST`
- `SMTP_PORT` (typically `587`)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `DIGEST_TO_EMAIL`
- `SMTP_FROM_EMAIL` (optional)

Do not commit credentials to the repository. No email is sent until the required secrets are configured.

## Sources and evidence

- WHO official announcements: https://www.who.int/news
- WHO Africa: https://www.afro.who.int/news
- PubMed API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- ClinicalTrials.gov API: https://clinicaltrials.gov/data-api/api

Research citations, trial registries and institutional announcements have different evidential value. The feed does **not** automatically verify clinical effectiveness or independently measure public health impact. Topic and region classification are rule-based and may require review.

## Limitations and safety

- The app is educational and is **not** clinical decision-support software.
- It should not receive identifiable patient records.
- The BI lab uses invented data solely for analytical practice.
- Country case studies are educational summaries and should be checked against original implementation reports before public citation.
- Source URLs and publication dates should be verified in the original publications.
- Bookmarks and roadmap data use browser-local storage; there is no cloud account.
- The HTML app is a lightweight first deployment. The previous downloadable prototype also contains additional presentation and interface work that can be ported later.

## Repository structure

```
docs/
  index.html
  data/
    updates.json
    status.json
    briefs.json
    brief_status.json (created after first briefing run)
scripts/
  generate_briefs.py
  update_feed.py
.github/workflows/
  daily-healthscope.yml
README.md
```

## Learning routine

Each day, read one original source, define two unfamiliar terms, ask whether the new intervention has actually demonstrated an outcome, and suggest one carefully defined metric to evaluate it in Power BI.
