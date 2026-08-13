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

# ---------- styling ----------
CSS = """
<style>
/* hide default streamlit chrome */
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 780px;}

/* hero header */
.hero {
    background: linear-gradient(135deg, #6d28d9 0%, #2563eb 100%);
    border-radius: 18px;
    padding: 30px 34px;
    color: #fff;
    margin-bottom: 22px;
    box-shadow: 0 10px 30px rgba(37,99,235,.25);
}
.hero h1 {margin: 0; font-size: 1.9rem; font-weight: 800; line-height: 1.2;}
.hero p {margin: 8px 0 0; font-size: 1.02rem; opacity: .92;}

/* section labels */
.section {font-weight: 700; font-size: 1.05rem; margin: 6px 0 2px;}

/* inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    border-radius: 10px !important;
}

/* primary button */
.stButton > button, .stDownloadButton > button {
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: .6rem 1rem !important;
}
div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #6d28d9 0%, #2563eb 100%) !important;
    border: none !important;
    font-size: 1.05rem !important;
    padding: .75rem 1rem !important;
    box-shadow: 0 6px 18px rgba(109,40,217,.35) !important;
}

/* result card */
.result-card {
    background: rgba(37,99,235,.06);
    border: 1px solid rgba(37,99,235,.18);
    border-radius: 14px;
    padding: 6px 18px 14px;
    margin-top: 8px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------- interface (UI) translations ----------
# UI language = language of the app's own labels/buttons.
# "Output language" field (below) = language of the GENERATED text.
UI_LANGS = {"English": "en", "Русский": "ru"}

T = {
    "en": {
        "title": "Product Description Generator",
        "caption": "Turn a few product details into ready-to-publish SEO listings for Shopify, Amazon & Etsy — in seconds.",
        "intro": "Just fill in your **product name** and a few details, then press **Generate**. Everything else is optional.",
        "pw_title": "🛒 Product Description Generator",
        "pw_prompt": "Enter access password",
        "pw_btn": "Enter",
        "pw_wrong": "Wrong password.",
        "gens_left": "✨ Generations left this session: **{n}** / {lim}",
        "sec_product": "1 · Your product",
        "sec_settings": "2 · Settings",
        "product_name": "Product name",
        "product_name_ph": "e.g. Handmade Ceramic Coffee Mug",
        "features": "Key features / details",
        "features_ph": "Material, size, color, benefits, what makes it special...",
        "marketplace": "Marketplace",
        "out_lang": "Output language",
        "adv": "⚙️  More options (optional)",
        "category": "Category",
        "category_ph": "e.g. Kitchen & Dining",
        "tone": "Tone",
        "keywords": "Focus keywords (comma-separated)",
        "keywords_ph": "ceramic mug, handmade gift",
        "photo": "📷 Upload a product photo — the AI reads it and writes the listing",
        "url": "🔗 Or paste a product page URL",
        "url_ph": "https://...",
        "generate": "✨ Generate my listing",
        "spinner": "Writing your listing...",
        "done": "✅ Your listing is ready — copy each section below.",
        "h_title": "SEO Title",
        "h_desc": "Description",
        "h_bullets": "Bullet Points",
        "h_tags": "Tags / Keywords",
        "h_meta": "Meta Description",
        "download": "⬇️ Download as JSON",
        "footer": "Powered by Google Gemini",
        "err_nokey": "GEMINI_API_KEY is not set in app secrets.",
        "err_limit": "Session limit reached. Come back later or upgrade.",
        "warn_input": "Give me something to work with: a product name, a photo, or a URL.",
        "warn_url": "Couldn't read that URL — using the other fields.",
        "err_format": "The AI returned an unexpected format. Please try again.",
        "tones": {"Professional": "Professional", "Friendly": "Friendly", "Luxury": "Luxury",
                  "Playful": "Playful", "Minimalist": "Minimalist"},
    },
    "ru": {
        "title": "Генератор описаний товаров",
        "caption": "Превратите пару деталей о товаре в готовые SEO-описания для Shopify, Amazon и Etsy — за секунды.",
        "intro": "Просто впишите **название товара** и пару деталей, затем нажмите **Сгенерировать**. Всё остальное — по желанию.",
        "pw_title": "🛒 Генератор описаний товаров",
        "pw_prompt": "Введите пароль доступа",
        "pw_btn": "Войти",
        "pw_wrong": "Неверный пароль.",
        "gens_left": "✨ Осталось генераций в этой сессии: **{n}** / {lim}",
        "sec_product": "1 · Ваш товар",
        "sec_settings": "2 · Настройки",
        "product_name": "Название товара",
        "product_name_ph": "напр. Керамическая кофейная кружка ручной работы",
        "features": "Ключевые характеристики / детали",
        "features_ph": "Материал, размер, цвет, преимущества, чем особенный...",
        "marketplace": "Площадка",
        "out_lang": "Язык результата",
        "adv": "⚙️  Больше настроек (необязательно)",
        "category": "Категория",
        "category_ph": "напр. Кухня и столовая",
        "tone": "Тон",
        "keywords": "Ключевые слова (через запятую)",
        "keywords_ph": "керамическая кружка, подарок ручной работы",
        "photo": "📷 Загрузите фото товара — ИИ прочитает его и напишет описание",
        "url": "🔗 Или вставьте ссылку на страницу товара",
        "url_ph": "https://...",
        "generate": "✨ Сгенерировать описание",
        "spinner": "Пишу ваше описание...",
        "done": "✅ Описание готово — скопируйте каждый раздел ниже.",
        "h_title": "SEO-заголовок",
        "h_desc": "Описание",
        "h_bullets": "Списком (буллеты)",
        "h_tags": "Теги / Ключевые слова",
        "h_meta": "Meta-описание",
        "download": "⬇️ Скачать в JSON",
        "footer": "Работает на Google Gemini",
        "err_nokey": "GEMINI_API_KEY не задан в секретах приложения.",
        "err_limit": "Лимит сессии исчерпан. Зайдите позже или оформите подписку.",
        "warn_input": "Дайте с чем работать: название товара, фото или ссылку.",
        "warn_url": "Не удалось прочитать эту ссылку — использую остальные поля.",
        "err_format": "ИИ вернул неожиданный формат. Попробуйте ещё раз.",
        "tones": {"Professional": "Деловой", "Friendly": "Дружелюбный", "Luxury": "Премиум",
                  "Playful": "Игривый", "Minimalist": "Минималистичный"},
    },
}

# ---------- UI language picker (top-right) ----------
_a, _b = st.columns([3, 1])
with _b:
    ui_lang_name = st.selectbox("🌐", list(UI_LANGS.keys()), label_visibility="collapsed", key="ui_lang")
t = T[UI_LANGS[ui_lang_name]]

# ---------- password gate ----------
def check_password() -> bool:
    if not APP_PASSWORD:
        return True
    if st.session_state.get("authed"):
        return True
    st.markdown(f"<div class='hero'><h1>{t['pw_title']}</h1></div>", unsafe_allow_html=True)
    pw = st.text_input(t["pw_prompt"], type="password")
    if st.button(t["pw_btn"], type="primary"):
        if pw == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error(t["pw_wrong"])
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
    return f"""You are a senior e-commerce SEO copywriter with 10+ years of experience writing high-converting, native-level product listings.

{img_line}Marketplace: {marketplace}
Marketplace guidance: {hint}
Output language: {language}
Desired tone: {tone}
Product name: {name or "(infer from the attached photo)"}
Category: {category or "(not specified)"}
Key features / details: {features or "(infer from the attached photo)"}
Focus keywords to weave in naturally (optional): {keywords or "(none provided)"}

Write compelling, original, SEO-optimized listing content. Avoid keyword stuffing, avoid false claims.

CRITICAL LANGUAGE RULE: Write EVERY field (seo_title, description, bullet_points, tags, meta_description) entirely in {language}. Every single word of the output must be in {language}. Do NOT use English unless {language} is "English". If focus keywords are in another language, translate/adapt them naturally into {language}.

Return STRICT JSON only, matching exactly this schema:
{{
  "seo_title": "string, <= 70 chars, keyword-rich, in {language}",
  "description": "string, persuasive paragraph(s) matching the marketplace guidance, in {language}",
  "bullet_points": ["string in {language}", "string", "string", "string", "string"],
  "tags": ["string in {language}", "..."],
  "meta_description": "string, <= 155 chars, in {language}"
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
st.markdown(f"<div class='hero'><h1>🛒 {t['title']}</h1><p>{t['caption']}</p></div>", unsafe_allow_html=True)

remaining = SESSION_LIMIT - st.session_state["used"]
st.info(t["gens_left"].format(n=max(remaining, 0), lim=SESSION_LIMIT))
st.markdown(t["intro"])

# --- essentials ---
st.markdown(f"<div class='section'>{t['sec_product']}</div>", unsafe_allow_html=True)
name = st.text_input(t["product_name"], placeholder=t["product_name_ph"])
features = st.text_area(t["features"], height=110, placeholder=t["features_ph"])

st.markdown(f"<div class='section'>{t['sec_settings']}</div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    marketplace = st.selectbox(t["marketplace"], ["Shopify", "Amazon", "Etsy"])
with c2:
    language = st.selectbox(t["out_lang"],
                            ["English", "Spanish", "French", "German", "Portuguese",
                             "Italian", "Chinese (Simplified)", "Japanese", "Arabic", "Russian"])

# --- optional / advanced ---
with st.expander(t["adv"]):
    category = st.text_input(t["category"], placeholder=t["category_ph"])
    tone_values = ["Professional", "Friendly", "Luxury", "Playful", "Minimalist"]
    tone = st.selectbox(t["tone"], tone_values, format_func=lambda v: t["tones"].get(v, v))
    keywords = st.text_input(t["keywords"], placeholder=t["keywords_ph"])
    photo = st.file_uploader(t["photo"], type=["jpg", "jpeg", "png"])
    if photo:
        st.image(photo, width=200)
    url = st.text_input(t["url"], placeholder=t["url_ph"])

st.write("")
if st.button(t["generate"], type="primary", use_container_width=True):
    img_bytes = photo.getvalue() if photo else None
    ctx = features
    if url.strip():
        try:
            ctx = (features + "\n\nExtracted from the product page:\n" + fetch_url_text(url.strip())).strip()
        except Exception:
            st.warning(t["warn_url"])
    if not API_KEY:
        st.error(t["err_nokey"])
    elif remaining <= 0:
        st.error(t["err_limit"])
    elif not img_bytes and not ctx.strip() and not name.strip():
        st.warning(t["warn_input"])
    else:
        with st.spinner(t["spinner"]):
            try:
                out = generate(
                    build_prompt(name, ctx, category, marketplace, tone, keywords,
                                 has_image=bool(img_bytes), language=language),
                    image_bytes=img_bytes,
                    image_mime=(photo.type if photo else None),
                )
                st.session_state["used"] += 1
                st.success(t["done"])

                st.markdown("<div class='result-card'>", unsafe_allow_html=True)
                st.subheader(t["h_title"])
                st.code(out.get("seo_title", ""), language=None)

                st.subheader(t["h_desc"])
                st.write(out.get("description", ""))

                st.subheader(t["h_bullets"])
                for b in out.get("bullet_points", []):
                    st.markdown(f"- {b}")

                st.subheader(t["h_tags"])
                st.code(", ".join(out.get("tags", [])), language=None)

                st.subheader(t["h_meta"])
                st.code(out.get("meta_description", ""), language=None)
                st.markdown("</div>", unsafe_allow_html=True)

                st.download_button(t["download"],
                                   data=json.dumps(out, ensure_ascii=False, indent=2),
                                   file_name="listing.json", mime="application/json")
            except json.JSONDecodeError:
                st.error(t["err_format"])
            except Exception as e:
                st.error(str(e))

st.divider()
st.caption(t["footer"])
