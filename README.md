# Product Description Generator (SaaS MVP)

Streamlit web app that turns raw product info into SEO-ready listings
(title, description, bullets, tags, meta) for Shopify / Amazon / Etsy.
Engine: Google Gemini. Infra cost: $0 (Streamlit Community Cloud).

## Files
- `app.py` — the whole app
- `requirements.txt` — dependencies

## Deploy (free, ~10 min) — do tomorrow
1. Create a free **GitHub** account, make a new repo, upload these files.
2. Go to **share.streamlit.io** (Streamlit Community Cloud) → New app → pick the repo → main file `app.py`.
3. In the app's **Settings → Secrets**, paste:
   ```
   GEMINI_API_KEY = "your_google_ai_studio_key"
   APP_PASSWORD   = "choose_a_password"
   GEMINI_MODEL   = "gemini-3.5-flash"
   SESSION_LIMIT  = "10"
   ```
4. Deploy → you get a public URL.

## Local test (optional, needs Python)
```
pip install -r requirements.txt
# put the same secrets in .streamlit/secrets.toml
streamlit run app.py
```

## Safety
- Password gate (APP_PASSWORD) so only you/customers get in.
- Per-session generation limit (SESSION_LIMIT) so nobody drains your API tokens.

## TODO (next session)
- Sam (Gemini): polished prompt templates per marketplace + Fiverr/Upwork sales copy.
- Optional: URL scraping input, "copy" buttons, custom branding, Stripe/paywall.
