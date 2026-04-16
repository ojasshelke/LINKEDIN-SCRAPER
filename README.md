# LINKEDIN SACRAPER

Streamlit app: **LinkedIn Post Finder** powered by the Apify actor [`benjarapi/linkedin-post-search`](https://apify.com/benjarapi/linkedin-post-search).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Apify token (recommended: `.env`)

1. Copy the example env file and edit it:

   ```bash
   cp .env.example .env
   ```

2. Put your token on one line (no quotes needed unless the token has spaces):

   ```
   APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. Run the app from the same folder as `.env`. The app calls `load_dotenv()` on startup so the sidebar token field is filled automatically.

`.env` is listed in `.gitignore` — **never commit** your real token.

**Alternative:** export in the shell before `streamlit run`:

```bash
export APIFY_TOKEN="your_apify_token_here"
```

**Streamlit Cloud:** add `APIFY_TOKEN` under app **Secrets** in the dashboard, or create `.streamlit/secrets.toml` locally (also gitignored if you add it to `.gitignore`).

### Security

If your token ever appeared in a URL, chat, or screenshot, **rotate it** in [Apify Console → Integrations](https://console.apify.com/settings/integrations) and update `.env`.

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
