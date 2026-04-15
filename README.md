# LINKEDIN SACRAPER

Streamlit app: **LinkedIn Post Finder** powered by the Apify actor [`benjarapi/linkedin-post-search`](https://apify.com/benjarapi/linkedin-post-search).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional: set your Apify token so the sidebar is pre-filled:

```bash
export APIFY_TOKEN="your_apify_token_here"
```

## Run

```bash
streamlit run app.py
```

## Features

- Dark glass UI, result cards with author, headline, reactions, post link
- Strict keyword filter so loose LinkedIn matches (e.g. wrong “Polaris” school) are dropped unless you turn the filter off
- CSV / Excel export

## Requirements

- Apify account and API token from [Apify Console](https://console.apify.com/settings/integrations)
