"""
Product Description Generator — SaaS MVP (Streamlit + Gemini)
Generates SEO-optimized product content (title, description, bullets, tags, meta)
for Shopify / Amazon / Etsy.

Deploy: push this folder to GitHub -> Streamlit Community Cloud -> add secrets.
Secrets (Streamlit Cloud -> App -> Settings -> Secrets):
    GEMINI_API_KEY = "your_google_ai_studio_key"
    APP_PASSWORD   = "choose_a_password"
    GEMINI_MODEL   = "gemini-3.5-flash"   # optional
    SESSION_LIMIT  = "10"                  # optional, generations per visitor session
"""

import json
import streamlit as st
import requests

# ---------- config ----------
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MODEL = st.secrets.get("GEMINI_MODEL", "gemini-3.5-flash")
SESSION_LIMIT = int(st.secrets.get("SESSION_LIMIT", "10"))
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

st.set_page_config(page_title="Product Description Generator", page_icon="🛒", layout="centered")

# ---------- password gate ----------
def check_password() -> bool:
    if not APP_PASSWORD:
        return True  # no password configured -> open
    if st.session_state.get("authed"):
        return True
    st.title("🛒 Product Description Generator")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False

if not check_password():
    st.stop()

# ---------- session usage limit ----------
if "used" not in st.session_state:
    st.session_state["used"] = 0

# ---------- prompt builder ----------
MARKET_HINTS = {
    "Shopify": "Direct-to-consumer store. Persuasive, brand-driven, benefit-led copy. Description ~120-180 words.",
    "Amazon": "Marketplace listing. Keyword-dense, scannable, feature+benefit bullets, compliant (no unverifiable claims). 5 strong bullets.",
    "Etsy": "Handmade/creative marketplace. Warm, story-driven, artisan tone, strong long-tail tags (Etsy allows up to 13 tags).",
}

def build_prompt(name, features, category, marketplace, tone, keywords, has_image=False, language="English"):
    hint = MARKET_HINTS.get(marketplace, "")
    img_line = ("A photo of the product is attached. Carefully analyze the image "
                "(product type, materials, colors, style, likely use-case) and base the "
                "listing on what you see. Use any text fields below as extra context.\n\n") if has_image else ""
    return f"""You are a senior e-commerce SEO copywriter with 10+ years of experience writing high-converting product listings in professional English.

{img_line}Marketplace: {marketplace}
Marketplace guidance: {hint}
Output language: {language}
Desired tone: {tone}
Product name: {name or "(infer from the attached photo)"}
Category: {category or "(not specified)"}
Key features / details: {features or "(infer from the attached photo)"}
Focus keywords to weave in naturally (optional): {keywords or "(none provided)"}

Write compelling, original, SEO-optimized listing content in {language}. Avoid keyword stuffing, avoid false claims. Return STRICT JSON only, matching exactly this schema:
{{
  "seo_title": "string, <= 70 chars, keyword-rich",
  "description": "string, persuasive paragraph(s) matching the marketplace guidance",
  "bullet_points": ["string", "string", "string", "string", "string"],
  "tags": ["string", ...],
  "meta_description": "string, <= 155 chars"
}}"""

def fetch_url_text(url: str) -> str:
    import re
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", r.text)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:6000]


def generate(prompt: str, image_bytes=None, image_mime=None) -> dict:
    import base64
    parts = [{"text": prompt}]
    if image_bytes:
        parts.append({"inline_data": {
            "mime_type": image_mime or "image/jpeg",
            "data": base64.b64encode(image_bytes).decode(),
        }})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }
    r = requests.post(API_URL, params={"key": API_KEY}, json=body, timeout=60)
    if r.status_code == 429:
        raise RuntimeError("The AI is rate-limited right now. Please wait a minute and try again.")
    if r.status_code != 200:
        raise RuntimeError(f"API error {r.status_code}: {r.text[:200]}")
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)

# ---------- UI ----------
st.title("🛒 Product Description Generator")
st.caption("Turn raw product info into ready-to-publish SEO listings for Shopify, Amazon & Etsy.")

remaining = SESSION_LIMIT - st.session_state["used"]
st.info(f"Generations left this session: **{max(remaining,0)}** / {SESSION_LIMIT}")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Product name *", placeholder="e.g. Handmade Ceramic Coffee Mug")
    category = st.text_input("Category", placeholder="e.g. Kitchen & Dining")
with col2:
    marketplace = st.selectbox("Marketplace", ["Shopify", "Amazon", "Etsy"])
    tone = st.selectbox("Tone", ["Professional", "Friendly", "Luxury", "Playful", "Minimalist"])

language = st.selectbox("Output language",
                        ["English", "Spanish", "French", "German", "Portuguese",
                         "Italian", "Chinese (Simplified)", "Japanese", "Arabic", "Russian"])
features = st.text_area("Key features / details", height=120,
                        placeholder="Material, size, color, benefits, what makes it special...")
keywords = st.text_input("Focus keywords (optional, comma-separated)", placeholder="ceramic mug, handmade gift")
photo = st.file_uploader("📷 Or upload a product photo — the AI analyzes it and writes the listing",
                         type=["jpg", "jpeg", "png"])
if photo:
    st.image(photo, width=220)
url = st.text_input("🔗 Or paste a product page URL — we'll read the page", placeholder="https://...")

if st.button("✨ Generate", type="primary", use_container_width=True):
    img_bytes = photo.getvalue() if photo else None
    ctx = features
    if url.strip():
        try:
            ctx = (features + "\n\nExtracted from the product page:\n" + fetch_url_text(url.strip())).strip()
        except Exception:
            st.warning("Couldn't read that URL — using the other fields.")
    if not API_KEY:
        st.error("GEMINI_API_KEY is not set in app secrets.")
    elif remaining <= 0:
        st.error("Session limit reached. Come back later or upgrade.")
    elif not img_bytes and not ctx.strip() and not name.strip():
        st.warning("Give me something to work with: a photo, a URL, or product name + features.")
    else:
        with st.spinner("Writing your listing..."):
            try:
                out = generate(
                    build_prompt(name, ctx, category, marketplace, tone, keywords,
                                 has_image=bool(img_bytes), language=language),
                    image_bytes=img_bytes,
                    image_mime=(photo.type if photo else None),
                )
                st.session_state["used"] += 1
                st.success("Done! Copy each section below.")

                st.subheader("SEO Title")
                st.code(out.get("seo_title", ""), language=None)

                st.subheader("Description")
                st.write(out.get("description", ""))

                st.subheader("Bullet Points")
                for b in out.get("bullet_points", []):
                    st.markdown(f"- {b}")

                st.subheader("Tags / Keywords")
                st.code(", ".join(out.get("tags", [])), language=None)

                st.subheader("Meta Description")
                st.code(out.get("meta_description", ""), language=None)

                st.download_button("⬇️ Download as JSON",
                                   data=json.dumps(out, ensure_ascii=False, indent=2),
                                   file_name="listing.json", mime="application/json")
            except json.JSONDecodeError:
                st.error("The AI returned an unexpected format. Please try again.")
            except Exception as e:
                st.error(str(e))

st.divider()
st.caption("Powered by Google Gemini · Built as a $0-infra SaaS MVP")
