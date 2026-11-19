# HealthScope — Global Healthcare Intelligence & Learning Hub

A source-linked healthcare learning application built for a developing healthcare data analyst and business intelligence developer.

**Current status:** Initial web application and daily public-source collector committed to GitHub. GitHub Pages still needs to be enabled in repository settings. The scheduled data ingestion has not yet been tested through an Actions run. Optional email requires SMTP secrets.

## Features

- Responsive browser-based dashboard and global healthcare reading feed
- Searchable dictionary of 30 healthcare, epidemiology, quality and BI terms
- Specific before/after country examples: Rwanda, Kenya, Bauchi State in Nigeria and South Africa
- Synthetic clinic analytics lab, KPI comparison and CSV export
- Four-week learning roadmap with progress stored locally in the browser
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

It saves public source metadata in `docs/data/updates.json` and source status in `docs/data/status.json`. It does not scrape full news articles or store patient data. Individual source failures are recorded without discarding the existing feed.

If the workflow cannot commit its data, check **Settings → Actions → General → Workflow permissions** to ensure the GitHub Actions token can write repository contents.

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
scripts/
  update_feed.py
.github/workflows/
  daily-healthscope.yml
README.md
```

## Learning routine

Each day, read one original source, define two unfamiliar terms, ask whether the new intervention has actually demonstrated an outcome, and suggest one carefully defined metric to evaluate it in Power BI.
