"""
Product Description Generator — SaaS MVP (Streamlit + Gemini)
Generates SEO-optimized product content (title, description, bullets, tags, meta)
for Shopify / Amazon / Etsy / eBay / Walmart / Vinted / etc.

Deploy: push this folder to GitHub -> Streamlit Community Cloud -> add secrets.
Secrets (Streamlit Cloud -> App -> Settings -> Secrets):
    GEMINI_API_KEY = "your_google_ai_studio_key"
    APP_PASSWORD   = "choose_a_password"
    GEMINI_MODEL   = "gemini-3.5-flash"   # optional
    SESSION_LIMIT  = "5"                   # optional, generations per visitor session (hard-capped at 5)
"""

import json
import time
import streamlit as st
import requests

# ---------- config ----------
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MODEL = st.secrets.get("GEMINI_MODEL", "gemini-3.5-flash")
# Free tier: 10 generations per visitor session (will become per-account after auth).
SESSION_LIMIT = min(int(st.secrets.get("SESSION_LIMIT", "10")), 10)
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

st.set_page_config(page_title="Product Description Generator", page_icon="•",
                   layout="centered", initial_sidebar_state="collapsed")

# ---------- styling ----------
CSS = """
<style>
/* hide default streamlit chrome */
#MainMenu, header {visibility: hidden;}
footer {display: none !important;}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], .stAppDeployButton {display: none !important;}
[data-testid="stElementToolbar"], [data-testid="stElementToolbarButton"] {display: none !important;}
[data-testid="StyledFullScreenButton"], [title="View fullscreen"], [aria-label="Fullscreen"] {display: none !important;}
a[href*="streamlit.io"], [class*="viewerBadge"] {display: none !important;}
.block-container, [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 760px !important; margin-left: auto !important; margin-right: auto !important;}
/* dark app background — removes the cheap white frame */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], body {background: #0e1117 !important;}
/* left panel: keep the open arrow visible; slim + tidy */
[data-testid="stSidebarCollapsedControl"] {display: flex !important; visibility: visible !important; opacity: 1 !important;}
section[data-testid="stSidebar"] {width: 300px !important; min-width: 300px !important; background: #0d1117;}
section[data-testid="stSidebar"] .block-container {padding: 1rem .7rem;}
section[data-testid="stSidebar"] h3 {font-size: 1rem;}

/* hero header — calm, muted, refined */
.hero {
    background: linear-gradient(135deg, #1f2937 0%, #312e81 100%);
    border-radius: 16px;
    padding: 30px 32px;
    color: #f8fafc;
    margin-bottom: 8px;
}
.hero h1 {margin: 0; font-size: 1.7rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.25;}
.hero p {margin: 10px 0 0; font-size: .97rem; line-height: 1.5; color: #cbd5e1;}

/* usage line */
.usage {text-align: right; font-size: .82rem; color: #94a3b8; margin: 2px 0 10px;}

/* section labels */
.section {font-weight: 600; font-size: 1.0rem; margin: 18px 0 4px; opacity: .9;}

/* inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    border-radius: 10px !important;
}

/* buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: 11px !important;
    font-weight: 600 !important;
    padding: .6rem 1rem !important;
}
div[data-testid="stButton"] button[kind="primary"] {
    background: #4f46e5 !important;
    border: none !important;
    color: #fff !important;
    font-size: 1.02rem !important;
    padding: .78rem 1rem !important;
    margin-top: .3rem !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {background: #4338ca !important;}

/* result card */
.result-card {
    background: rgba(79,70,229,.05);
    border: 1px solid rgba(79,70,229,.16);
    border-radius: 14px;
    padding: 4px 18px 14px;
    margin-top: 10px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------- Supabase auth (email + password) ----------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://jpghxxnnvrbqzdmbkpqj.supabase.co").rstrip("/")
SUPABASE_ANON = st.secrets.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpwZ2h4eG5udnJicXpkbWJrcHFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY2NTE4ODUsImV4cCI6MjEwMjIyNzg4NX0."
    "4onnBIv-j8RC0LVIGsGpVCAHeMlSu0qbP1ewyTXJG5A",
)
SB_HEADERS = {"apikey": SUPABASE_ANON, "Content-Type": "application/json"}

# Browser persistence ("remember me") is disabled — safe no-op helpers keep the
# rest of the auth code working within a session (session-only login).
_LS = None

def _ls_get(k):
    if not _LS:
        return None
    try:
        v = _LS.getItem(k)
        return v or None
    except Exception:
        return None

def _ls_set(k, v):
    if not _LS:
        return
    try:
        _LS.setItem(k, v, key=f"lsset_{k}")
    except Exception:
        pass

AUTH = {
    "en": {
        "title": "Create an account to use the generator",
        "sub": "Sign in or register — you get 10 free generations.",
        "signin": "Sign in", "register": "Register",
        "email": "Email", "password": "Password", "first": "First name", "last": "Last name",
        "signin_btn": "Sign in", "register_btn": "Create account",
        "err_login": "Wrong email or password.",
        "err_register": "Could not register. Try another email or a stronger password (min 6 characters).",
        "check_email": "Account created. Please confirm your email, then sign in.",
        "logout": "Log out", "hi": "Hi, {name}",
        "account": "Account", "history_title": "Your listings", "clear": "Clear listings",
        "history_empty": "Your generated listings will appear here.",
        "resets_in": "· free generations reset in {h}h {m}m",
        "forgot": "Forgot your password?",
        "recover_btn": "Send reset link",
        "recover_sent": "If an account exists for that email, a password-reset link has been sent. Check your inbox (and spam).",
        "set_new_pw": "Set a new password",
        "new_pw_ph": "New password (min 6 characters)",
        "update_pw_btn": "Update password",
        "pw_updated": "Password updated. You can sign in now with your new password.",
        "pw_update_err": "Could not update the password. The reset link may have expired — request a new one.",
    },
    "ru": {
        "title": "Создайте аккаунт, чтобы пользоваться генератором",
        "sub": "Войдите или зарегистрируйтесь — 10 бесплатных генераций.",
        "signin": "Вход", "register": "Регистрация",
        "email": "Email", "password": "Пароль", "first": "Имя", "last": "Фамилия",
        "signin_btn": "Войти", "register_btn": "Создать аккаунт",
        "err_login": "Неверная почта или пароль.",
        "err_register": "Не удалось зарегистрироваться. Другая почта или пароль надёжнее (мин. 6 символов).",
        "check_email": "Аккаунт создан. Подтвердите почту и войдите.",
        "logout": "Выйти", "hi": "Привет, {name}",
        "account": "Аккаунт", "history_title": "Ваши описания", "clear": "Очистить описания",
        "history_empty": "Здесь появятся сгенерированные описания.",
        "resets_in": "· бесплатные обновятся через {h}ч {m}м",
        "forgot": "Забыли пароль?",
        "recover_btn": "Отправить ссылку для сброса",
        "recover_sent": "Если аккаунт с такой почтой существует, письмо со ссылкой для сброса пароля отправлено. Проверьте почту (и спам).",
        "set_new_pw": "Задайте новый пароль",
        "new_pw_ph": "Новый пароль (минимум 6 символов)",
        "update_pw_btn": "Сохранить новый пароль",
        "pw_updated": "Пароль обновлён. Теперь войдите с новым паролем.",
        "pw_update_err": "Не удалось обновить пароль. Возможно, ссылка устарела — запросите новую.",
    },
}

def _sb_apply_session(data: dict):
    user = data.get("user") or data
    meta = (user.get("user_metadata") or {}) if isinstance(user, dict) else {}
    st.session_state["sb_token"] = data.get("access_token", "")
    st.session_state["sb_name"] = meta.get("first_name") or (user.get("email", "") or "").split("@")[0]
    try:
        st.session_state["used"] = int(meta.get("used") or 0)
    except (TypeError, ValueError):
        st.session_state["used"] = 0
    try:
        st.session_state["period_start"] = float(meta.get("period_start") or 0)
    except (TypeError, ValueError):
        st.session_state["period_start"] = 0.0
    rt = data.get("refresh_token")
    if rt:
        st.session_state["sb_rt"] = rt
        _ls_set("sb_rt", rt)

def sb_refresh(rt):
    return requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                         headers=SB_HEADERS, json={"refresh_token": rt}, timeout=30)

def sb_login(email, password):
    return requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                         headers=SB_HEADERS, json={"email": email, "password": password}, timeout=30)

def sb_signup(email, password, first, last):
    return requests.post(f"{SUPABASE_URL}/auth/v1/signup", headers=SB_HEADERS,
                         json={"email": email, "password": password,
                               "data": {"first_name": first, "last_name": last, "used": 0}}, timeout=30)

def sb_recover(email):
    # Sends a Supabase password-reset email. Returns 200 regardless of whether the
    # email exists (anti-enumeration), so we always show the same neutral message.
    return requests.post(f"{SUPABASE_URL}/auth/v1/recover", headers=SB_HEADERS,
                         json={"email": email}, timeout=30)

def sb_update_password(access_token, new_password):
    # Uses the short-lived recovery access_token from the reset link to set a new password.
    return requests.put(f"{SUPABASE_URL}/auth/v1/user",
                        headers={**SB_HEADERS, "Authorization": f"Bearer {access_token}"},
                        json={"password": new_password}, timeout=30)

def _recovery_bridge():
    # Supabase puts the recovery token in the URL hash (#access_token=...&type=recovery),
    # which Streamlit can't read server-side. This tiny script moves it into a query
    # param and reloads, so Python can pick it up via st.query_params. Fails silently.
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        try {
          var h = (window.parent.location.hash || "");
          if (h.indexOf("access_token") !== -1 && h.indexOf("recovery") !== -1) {
            var p = new URLSearchParams(h.replace(/^#/, ""));
            var at = p.get("access_token");
            if (at) {
              var base = window.parent.location.href.split("#")[0].split("?")[0];
              window.parent.location.replace(base + "?recovery_at=" + encodeURIComponent(at));
            }
          }
        } catch (e) {}
        </script>
        """,
        height=0,
    )

def sb_set_usage(used, period_start):
    tok = st.session_state.get("sb_token")
    if not tok:
        return
    try:
        requests.put(f"{SUPABASE_URL}/auth/v1/user",
                     headers={**SB_HEADERS, "Authorization": f"Bearer {tok}"},
                     json={"data": {"used": used, "period_start": period_start}}, timeout=30)
    except Exception:
        pass

def render_auth(a):
    # Password-recovery step: if we arrived from a reset link, run the hash->query
    # bridge and, once the token is in the query, show a "set new password" form.
    _recovery_bridge()
    _rec_at = st.query_params.get("recovery_at")
    if _rec_at:
        st.markdown(f"<div class='hero'><h1>{a.get('set_new_pw', 'Set a new password')}</h1></div>",
                    unsafe_allow_html=True)
        _np = st.text_input(a.get("new_pw_ph", "New password"), type="password", key="np_new")
        if st.button(a.get("update_pw_btn", "Update password"), type="primary", key="np_btn"):
            if len(_np or "") < 6:
                st.warning(a.get("new_pw_ph", "New password"))
            else:
                try:
                    _ur = sb_update_password(_rec_at, _np)
                    if _ur.status_code == 200:
                        st.session_state["pw_reset_ok"] = True
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(a.get("pw_update_err", "Could not update the password."))
                except Exception:
                    st.error(a.get("pw_update_err", "Could not update the password."))
        return

    st.markdown(f"<div class='hero'><h1>{a['title']}</h1><p>{a['sub']}</p></div>", unsafe_allow_html=True)
    tab_in, tab_up = st.tabs([a["signin"], a["register"]])
    with tab_in:
        if st.session_state.pop("pw_reset_ok", False):
            st.success(a.get("pw_updated", "Password updated. Sign in with your new password."))
        e = st.text_input(a["email"], key="li_e")
        p = st.text_input(a["password"], type="password", key="li_p")
        if st.button(a["signin_btn"], type="primary", key="li_btn"):
            r = sb_login(e.strip(), p)
            if r.status_code == 200 and r.json().get("access_token"):
                _sb_apply_session(r.json())
                st.rerun()
            else:
                st.error(a["err_login"])
        with st.expander(a.get("forgot", "Forgot your password?")):
            re_ = st.text_input(a["email"], key="rec_e")
            if st.button(a.get("recover_btn", "Send reset link"), key="rec_btn"):
                if re_ and "@" in re_:
                    try:
                        sb_recover(re_.strip())
                    except Exception:
                        pass
                    st.success(a.get("recover_sent", "If an account exists for that email, a reset link has been sent."))
                else:
                    st.warning(a["email"])
    with tab_up:
        fn = st.text_input(a["first"], key="rg_f")
        ln = st.text_input(a["last"], key="rg_l")
        e2 = st.text_input(a["email"], key="rg_e")
        p2 = st.text_input(a["password"], type="password", key="rg_p")
        if st.button(a["register_btn"], type="primary", key="rg_btn"):
            r = sb_signup(e2.strip(), p2, fn.strip(), ln.strip())
            if r.status_code in (200, 201):
                data = r.json()
                if data.get("access_token"):
                    _sb_apply_session(data)
                    st.rerun()
                else:
                    r2 = sb_login(e2.strip(), p2)
                    if r2.status_code == 200 and r2.json().get("access_token"):
                        _sb_apply_session(r2.json())
                        st.rerun()
                    else:
                        st.info(a["check_email"])
            else:
                try:
                    msg = r.json().get("msg") or r.json().get("error_description") or a["err_register"]
                except Exception:
                    msg = a["err_register"]
                st.error(msg)

# ---------- interface (UI) translations ----------
# UI language = language of the app's own labels/buttons.
# "Output language" field (below) = language of the GENERATED text.
UI_LANGS = {
    "English": "en", "Русский": "ru", "Español": "es", "Français": "fr",
    "Deutsch": "de", "Italiano": "it", "Português": "pt",
}

T = {
    "en": {
        "title": "Product Description Generator",
        "caption": "Turn a few product details into ready-to-publish SEO listings for Shopify, Amazon, Etsy and more — in seconds.",
        "intro": "Fastest way: **upload a product photo** or **paste a product URL** — the AI does the rest. Or describe the product yourself below.",
        "or_manual": "Or describe the product manually",
        "pw_title": "Product Description Generator",
        "pw_prompt": "Enter access password", "pw_btn": "Enter", "pw_wrong": "Wrong password.",
        "gens_left": "Generations left this session: {n} / {lim}",
        "sec_product": "Your product", "sec_settings": "Settings",
        "product_name": "Product name", "product_name_ph": "e.g. Handmade Ceramic Coffee Mug",
        "features": "Key features / details", "features_ph": "Material, size, color, benefits, what makes it special...",
        "marketplace": "Marketplace", "out_lang": "Output language",
        "adv": "More options (optional)",
        "category": "Category", "category_ph": "e.g. Kitchen & Dining",
        "tone": "Tone", "keywords": "Focus keywords (comma-separated)", "keywords_ph": "ceramic mug, handmade gift",
        "photo": "Upload a product photo — the AI reads it and writes the listing",
        "url": "Or paste a product page URL", "url_ph": "https://...",
        "generate": "Generate my listing", "spinner": "Writing your listing...",
        "done": "Your listing is ready — copy each section below.",
        "h_title": "SEO Title", "h_desc": "Description", "h_bullets": "Bullet Points",
        "h_tags": "Tags / Keywords", "h_meta": "Meta Description",
        "download": "Download as JSON", "footer": "Powered by Google Gemini",
        "err_nokey": "GEMINI_API_KEY is not set in app secrets.",
        "err_limit": "Session limit reached. Come back later or upgrade.",
        "warn_input": "Give me something to work with: a product name, a photo, or a URL.",
        "warn_url": "Couldn't read that URL — using the other fields.",
        "err_format": "The AI returned an unexpected format. Please try again.",
        "warn_partial": "Only {done} of {total} photos processed — you've reached your free limit.",
        "photo_result": "Listing for: {name}",
        "bulk": "Bulk — photos of several different products",
        "bulk_hint": "Upload up to 10 photos of different products at once — you'll get a separate listing for each. This overrides the single photo above.",
        "tones": {"Professional": "Professional", "Friendly": "Friendly", "Luxury": "Luxury",
                  "Playful": "Playful", "Minimalist": "Minimalist"},
    },
    "ru": {
        "title": "Генератор описаний товаров",
        "caption": "Превратите пару деталей о товаре в готовые SEO-описания для Shopify, Amazon, Etsy и других — за секунды.",
        "intro": "Самый быстрый способ: **загрузите фото товара** или **вставьте ссылку** — остальное сделает ИИ. Или опишите товар вручную ниже.",
        "or_manual": "Или опишите товар вручную",
        "pw_title": "Генератор описаний товаров",
        "pw_prompt": "Введите пароль доступа", "pw_btn": "Войти", "pw_wrong": "Неверный пароль.",
        "gens_left": "Осталось генераций в этой сессии: {n} / {lim}",
        "sec_product": "Ваш товар", "sec_settings": "Настройки",
        "product_name": "Название товара", "product_name_ph": "напр. Керамическая кофейная кружка ручной работы",
        "features": "Ключевые характеристики / детали", "features_ph": "Материал, размер, цвет, преимущества, чем особенный...",
        "marketplace": "Площадка", "out_lang": "Язык результата",
        "adv": "Больше настроек (необязательно)",
        "category": "Категория", "category_ph": "напр. Кухня и столовая",
        "tone": "Тон", "keywords": "Ключевые слова (через запятую)", "keywords_ph": "керамическая кружка, подарок ручной работы",
        "photo": "Загрузите фото товара — ИИ прочитает его и напишет описание",
        "url": "Или вставьте ссылку на страницу товара", "url_ph": "https://...",
        "generate": "Сгенерировать описание", "spinner": "Пишу ваше описание...",
        "done": "Описание готово — скопируйте каждый раздел ниже.",
        "h_title": "SEO-заголовок", "h_desc": "Описание", "h_bullets": "Списком (буллеты)",
        "h_tags": "Теги / Ключевые слова", "h_meta": "Meta-описание",
        "download": "Скачать в JSON", "footer": "Работает на Google Gemini",
        "err_nokey": "GEMINI_API_KEY не задан в секретах приложения.",
        "err_limit": "Лимит сессии исчерпан. Зайдите позже или оформите подписку.",
        "warn_input": "Дайте с чем работать: название товара, фото или ссылку.",
        "warn_url": "Не удалось прочитать эту ссылку — использую остальные поля.",
        "err_format": "ИИ вернул неожиданный формат. Попробуйте ещё раз.",
        "warn_partial": "Обработано {done} из {total} фото — достигнут бесплатный лимит.",
        "photo_result": "Описание для: {name}",
        "bulk": "Пакет — фото нескольких разных товаров",
        "bulk_hint": "Загрузите сразу до 10 фото разных товаров — на каждое получите отдельное описание. Это заменяет одиночное фото выше.",
        "tones": {"Professional": "Деловой", "Friendly": "Дружелюбный", "Luxury": "Премиум",
                  "Playful": "Игривый", "Minimalist": "Минималистичный"},
    },
    "es": {
        "title": "Generador de descripciones de productos",
        "caption": "Convierte unos pocos datos del producto en fichas SEO listas para publicar en Shopify, Amazon, Etsy y más — en segundos.",
        "intro": "La forma más rápida: **sube una foto del producto** o **pega una URL** — la IA hace el resto. O describe el producto tú mismo abajo.",
        "or_manual": "O describe el producto manualmente",
        "pw_title": "Generador de descripciones de productos",
        "pw_prompt": "Introduce la contraseña de acceso", "pw_btn": "Entrar", "pw_wrong": "Contraseña incorrecta.",
        "gens_left": "Generaciones restantes en esta sesión: {n} / {lim}",
        "sec_product": "Tu producto", "sec_settings": "Ajustes",
        "product_name": "Nombre del producto", "product_name_ph": "p. ej. Taza de café de cerámica hecha a mano",
        "features": "Características / detalles clave", "features_ph": "Material, tamaño, color, ventajas, qué lo hace especial...",
        "marketplace": "Marketplace", "out_lang": "Idioma del resultado",
        "adv": "Más opciones (opcional)",
        "category": "Categoría", "category_ph": "p. ej. Cocina y comedor",
        "tone": "Tono", "keywords": "Palabras clave (separadas por comas)", "keywords_ph": "taza cerámica, regalo hecho a mano",
        "photo": "Sube una foto del producto — la IA la analiza y escribe la ficha",
        "url": "O pega la URL de la página del producto", "url_ph": "https://...",
        "generate": "Generar mi ficha", "spinner": "Escribiendo tu ficha...",
        "done": "Tu ficha está lista — copia cada sección abajo.",
        "h_title": "Título SEO", "h_desc": "Descripción", "h_bullets": "Puntos destacados",
        "h_tags": "Etiquetas / Palabras clave", "h_meta": "Meta descripción",
        "download": "Descargar en JSON", "footer": "Con la tecnología de Google Gemini",
        "err_nokey": "GEMINI_API_KEY no está configurada en los secretos de la app.",
        "err_limit": "Límite de sesión alcanzado. Vuelve más tarde o mejora tu plan.",
        "warn_input": "Dame algo con qué trabajar: nombre del producto, foto o URL.",
        "warn_url": "No se pudo leer esa URL — usando los demás campos.",
        "err_format": "La IA devolvió un formato inesperado. Inténtalo de nuevo.",
        "tones": {"Professional": "Profesional", "Friendly": "Cercano", "Luxury": "Lujo",
                  "Playful": "Desenfadado", "Minimalist": "Minimalista"},
    },
    "fr": {
        "title": "Générateur de descriptions produit",
        "caption": "Transformez quelques infos produit en fiches SEO prêtes à publier sur Shopify, Amazon, Etsy et plus — en quelques secondes.",
        "intro": "Le plus rapide : **importez une photo du produit** ou **collez une URL** — l'IA fait le reste. Ou décrivez le produit vous-même ci-dessous.",
        "or_manual": "Ou décrivez le produit manuellement",
        "pw_title": "Générateur de descriptions produit",
        "pw_prompt": "Saisissez le mot de passe d'accès", "pw_btn": "Entrer", "pw_wrong": "Mot de passe incorrect.",
        "gens_left": "Générations restantes cette session : {n} / {lim}",
        "sec_product": "Votre produit", "sec_settings": "Paramètres",
        "product_name": "Nom du produit", "product_name_ph": "ex. Mug en céramique fait main",
        "features": "Caractéristiques / détails clés", "features_ph": "Matériau, taille, couleur, avantages, ce qui le rend unique...",
        "marketplace": "Marketplace", "out_lang": "Langue du résultat",
        "adv": "Plus d'options (facultatif)",
        "category": "Catégorie", "category_ph": "ex. Cuisine et salle à manger",
        "tone": "Ton", "keywords": "Mots-clés (séparés par des virgules)", "keywords_ph": "mug céramique, cadeau fait main",
        "photo": "Importez une photo du produit — l'IA l'analyse et rédige la fiche",
        "url": "Ou collez l'URL de la page produit", "url_ph": "https://...",
        "generate": "Générer ma fiche", "spinner": "Rédaction de votre fiche...",
        "done": "Votre fiche est prête — copiez chaque section ci-dessous.",
        "h_title": "Titre SEO", "h_desc": "Description", "h_bullets": "Points clés",
        "h_tags": "Tags / Mots-clés", "h_meta": "Méta description",
        "download": "Télécharger en JSON", "footer": "Propulsé par Google Gemini",
        "err_nokey": "GEMINI_API_KEY n'est pas défini dans les secrets de l'app.",
        "err_limit": "Limite de session atteinte. Revenez plus tard ou passez à l'offre supérieure.",
        "warn_input": "Donnez-moi de quoi travailler : nom du produit, photo ou URL.",
        "warn_url": "Impossible de lire cette URL — utilisation des autres champs.",
        "err_format": "L'IA a renvoyé un format inattendu. Réessayez.",
        "tones": {"Professional": "Professionnel", "Friendly": "Amical", "Luxury": "Luxe",
                  "Playful": "Ludique", "Minimalist": "Minimaliste"},
    },
    "de": {
        "title": "Produktbeschreibungs-Generator",
        "caption": "Verwandeln Sie ein paar Produktangaben in Sekunden in veröffentlichungsfertige SEO-Listings für Shopify, Amazon, Etsy und mehr.",
        "intro": "Am schnellsten: **Produktfoto hochladen** oder **URL einfügen** — die KI erledigt den Rest. Oder beschreiben Sie das Produkt unten selbst.",
        "or_manual": "Oder beschreiben Sie das Produkt manuell",
        "pw_title": "Produktbeschreibungs-Generator",
        "pw_prompt": "Zugangspasswort eingeben", "pw_btn": "Anmelden", "pw_wrong": "Falsches Passwort.",
        "gens_left": "Verbleibende Generierungen in dieser Sitzung: {n} / {lim}",
        "sec_product": "Ihr Produkt", "sec_settings": "Einstellungen",
        "product_name": "Produktname", "product_name_ph": "z. B. Handgemachte Kaffeetasse aus Keramik",
        "features": "Wichtige Merkmale / Details", "features_ph": "Material, Größe, Farbe, Vorteile, was es besonders macht...",
        "marketplace": "Marktplatz", "out_lang": "Sprache des Ergebnisses",
        "adv": "Mehr Optionen (optional)",
        "category": "Kategorie", "category_ph": "z. B. Küche & Esszimmer",
        "tone": "Tonalität", "keywords": "Keywords (durch Kommas getrennt)", "keywords_ph": "Keramiktasse, handgemachtes Geschenk",
        "photo": "Produktfoto hochladen — die KI analysiert es und schreibt das Listing",
        "url": "Oder Produktseiten-URL einfügen", "url_ph": "https://...",
        "generate": "Listing generieren", "spinner": "Ihr Listing wird geschrieben...",
        "done": "Ihr Listing ist fertig — kopieren Sie jeden Abschnitt unten.",
        "h_title": "SEO-Titel", "h_desc": "Beschreibung", "h_bullets": "Stichpunkte",
        "h_tags": "Tags / Keywords", "h_meta": "Meta-Beschreibung",
        "download": "Als JSON herunterladen", "footer": "Unterstützt von Google Gemini",
        "err_nokey": "GEMINI_API_KEY ist in den App-Secrets nicht gesetzt.",
        "err_limit": "Sitzungslimit erreicht. Kommen Sie später wieder oder upgraden Sie.",
        "warn_input": "Geben Sie mir etwas zum Arbeiten: Produktname, Foto oder URL.",
        "warn_url": "Diese URL konnte nicht gelesen werden — die anderen Felder werden verwendet.",
        "err_format": "Die KI hat ein unerwartetes Format zurückgegeben. Bitte erneut versuchen.",
        "tones": {"Professional": "Professionell", "Friendly": "Freundlich", "Luxury": "Luxuriös",
                  "Playful": "Verspielt", "Minimalist": "Minimalistisch"},
    },
    "it": {
        "title": "Generatore di descrizioni prodotto",
        "caption": "Trasforma pochi dati sul prodotto in schede SEO pronte da pubblicare su Shopify, Amazon, Etsy e altri — in pochi secondi.",
        "intro": "Il modo più rapido: **carica una foto del prodotto** o **incolla un URL** — l'IA fa il resto. Oppure descrivi il prodotto tu stesso qui sotto.",
        "or_manual": "Oppure descrivi il prodotto manualmente",
        "pw_title": "Generatore di descrizioni prodotto",
        "pw_prompt": "Inserisci la password di accesso", "pw_btn": "Entra", "pw_wrong": "Password errata.",
        "gens_left": "Generazioni rimaste in questa sessione: {n} / {lim}",
        "sec_product": "Il tuo prodotto", "sec_settings": "Impostazioni",
        "product_name": "Nome del prodotto", "product_name_ph": "es. Tazza da caffè in ceramica fatta a mano",
        "features": "Caratteristiche / dettagli principali", "features_ph": "Materiale, dimensioni, colore, vantaggi, cosa lo rende speciale...",
        "marketplace": "Marketplace", "out_lang": "Lingua del risultato",
        "adv": "Altre opzioni (facoltativo)",
        "category": "Categoria", "category_ph": "es. Cucina e sala da pranzo",
        "tone": "Tono", "keywords": "Parole chiave (separate da virgole)", "keywords_ph": "tazza ceramica, regalo fatto a mano",
        "photo": "Carica una foto del prodotto — l'IA la analizza e scrive la scheda",
        "url": "Oppure incolla l'URL della pagina prodotto", "url_ph": "https://...",
        "generate": "Genera la scheda", "spinner": "Sto scrivendo la tua scheda...",
        "done": "La tua scheda è pronta — copia ogni sezione qui sotto.",
        "h_title": "Titolo SEO", "h_desc": "Descrizione", "h_bullets": "Punti elenco",
        "h_tags": "Tag / Parole chiave", "h_meta": "Meta descrizione",
        "download": "Scarica in JSON", "footer": "Basato su Google Gemini",
        "err_nokey": "GEMINI_API_KEY non è impostata nei secrets dell'app.",
        "err_limit": "Limite di sessione raggiunto. Torna più tardi o passa a un piano superiore.",
        "warn_input": "Dammi qualcosa su cui lavorare: nome del prodotto, foto o URL.",
        "warn_url": "Impossibile leggere quell'URL — uso gli altri campi.",
        "err_format": "L'IA ha restituito un formato inatteso. Riprova.",
        "tones": {"Professional": "Professionale", "Friendly": "Amichevole", "Luxury": "Lusso",
                  "Playful": "Giocoso", "Minimalist": "Minimalista"},
    },
    "pt": {
        "title": "Gerador de descrições de produtos",
        "caption": "Transforme alguns dados do produto em anúncios SEO prontos para publicar na Shopify, Amazon, Etsy e mais — em segundos.",
        "intro": "A forma mais rápida: **envie uma foto do produto** ou **cole um URL** — a IA faz o resto. Ou descreva o produto você mesmo abaixo.",
        "or_manual": "Ou descreva o produto manualmente",
        "pw_title": "Gerador de descrições de produtos",
        "pw_prompt": "Insira a senha de acesso", "pw_btn": "Entrar", "pw_wrong": "Senha incorreta.",
        "gens_left": "Gerações restantes nesta sessão: {n} / {lim}",
        "sec_product": "Seu produto", "sec_settings": "Configurações",
        "product_name": "Nome do produto", "product_name_ph": "ex. Caneca de café de cerâmica feita à mão",
        "features": "Características / detalhes principais", "features_ph": "Material, tamanho, cor, benefícios, o que o torna especial...",
        "marketplace": "Marketplace", "out_lang": "Idioma do resultado",
        "adv": "Mais opções (opcional)",
        "category": "Categoria", "category_ph": "ex. Cozinha e sala de jantar",
        "tone": "Tom", "keywords": "Palavras-chave (separadas por vírgulas)", "keywords_ph": "caneca cerâmica, presente artesanal",
        "photo": "Envie uma foto do produto — a IA analisa e escreve o anúncio",
        "url": "Ou cole o URL da página do produto", "url_ph": "https://...",
        "generate": "Gerar meu anúncio", "spinner": "Escrevendo seu anúncio...",
        "done": "Seu anúncio está pronto — copie cada seção abaixo.",
        "h_title": "Título SEO", "h_desc": "Descrição", "h_bullets": "Tópicos",
        "h_tags": "Tags / Palavras-chave", "h_meta": "Meta descrição",
        "download": "Baixar em JSON", "footer": "Desenvolvido com Google Gemini",
        "err_nokey": "GEMINI_API_KEY não está definida nos secrets do app.",
        "err_limit": "Limite da sessão atingido. Volte mais tarde ou faça upgrade.",
        "warn_input": "Dê-me algo para trabalhar: nome do produto, foto ou URL.",
        "warn_url": "Não foi possível ler esse URL — usando os outros campos.",
        "err_format": "A IA retornou um formato inesperado. Tente novamente.",
        "tones": {"Professional": "Profissional", "Friendly": "Amigável", "Luxury": "Luxo",
                  "Playful": "Descontraído", "Minimalist": "Minimalista"},
    },
}

# ---------- UI language picker (top-right) ----------
_a, _b = st.columns([3, 1])
with _b:
    ui_lang_name = st.selectbox("Language", list(UI_LANGS.keys()), label_visibility="collapsed", key="ui_lang")
t = T[UI_LANGS[ui_lang_name]]

# ---------- auth gate (Supabase: email + password) ----------
a = AUTH.get(UI_LANGS[ui_lang_name], AUTH["en"])

# Remember me: restore a saved session from the browser before showing the login screen.
if not st.session_state.get("sb_token"):
    _rt = st.session_state.get("sb_rt") or _ls_get("sb_rt")
    if _rt:
        try:
            _rr = sb_refresh(_rt)
            if _rr.status_code == 200 and _rr.json().get("access_token"):
                _sb_apply_session(_rr.json())
        except Exception:
            pass

if not st.session_state.get("sb_token"):
    render_auth(a)
    st.stop()

# ---------- session usage limit ----------
if "used" not in st.session_state:
    st.session_state["used"] = 0

# 24-hour rolling free quota: reset the counter once 24h pass since the period start.
_now = time.time()
_ps = st.session_state.get("period_start") or 0
if not _ps:
    st.session_state["period_start"] = _now
    sb_set_usage(st.session_state.get("used", 0), _now)
elif _now - _ps >= 86400:
    st.session_state["used"] = 0
    st.session_state["period_start"] = _now
    sb_set_usage(0, _now)

# ---------- prompt builder ----------
MARKET_HINTS = {
    "Shopify": "Direct-to-consumer store. Persuasive, brand-driven, benefit-led copy. Description ~120-180 words.",
    "Amazon": "Marketplace listing. Keyword-dense, scannable, feature+benefit bullets, compliant (no unverifiable claims). 5 strong bullets.",
    "Etsy": "Handmade/creative marketplace. Warm, story-driven, artisan tone, strong long-tail tags (Etsy allows up to 13 tags).",
    "eBay": "Global auction/fixed-price marketplace. Clear keyword-rich title (up to 80 chars), factual condition and spec details, scannable bullets.",
    "Walmart": "Large US marketplace. Concise, compliant, keyword-optimized title and feature bullets; clear family-friendly tone.",
    "Vinted": "Second-hand fashion marketplace (Europe). Casual, honest, concise. Highlight brand, size, condition, material; friendly peer-to-peer tone.",
    "AliExpress": "Global budget marketplace. Keyword-dense, spec-focused, many long-tail tags, plain and clear wording.",
    "Allegro": "Leading Polish/Central-European marketplace. Precise, spec-driven, keyword-rich title and bullets; trustworthy tone.",
    "Wildberries": "Large marketplace (CIS/Eastern Europe). Keyword-rich, benefit-led, well-structured bullets; clear and persuasive.",
    "Bol.com": "Leading Benelux marketplace. Clear, informative, benefit-led copy with correct product specs; trustworthy tone.",
}
MARKETPLACES = ["Shopify", "Amazon", "Etsy", "eBay", "Walmart", "Vinted", "AliExpress", "Allegro", "Wildberries", "Bol.com"]

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


GEN_MODELS = [MODEL, "gemini-3-flash-preview", "gemini-3.1-flash-lite"]

def generate(prompt: str, image_bytes=None, image_mime=None) -> dict:
    import base64, time
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
    # Try each model with a couple of retries; fall back on overload/transient errors.
    for m in GEN_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, params={"key": API_KEY}, json=body, timeout=60)
            except Exception:
                time.sleep(1.2 * (attempt + 1))
                continue
            if r.status_code == 200:
                try:
                    data = r.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
                except Exception:
                    time.sleep(1.0)
                    continue  # bad/partial response — retry
            if r.status_code in (429, 500, 502, 503):
                time.sleep(1.5 * (attempt + 1))  # overloaded/rate-limited — back off and retry
                continue
            raise RuntimeError(f"API error {r.status_code}: {r.text[:200]}")
    raise RuntimeError("The AI is very busy right now (high demand). Please try again in a minute.")

def render_result(out, t, dl_key, label=""):
    if label:
        st.markdown(f"**{t.get('photo_result', T['en']['photo_result']).format(name=label)}**")
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
    st.download_button(t["download"], data=json.dumps(out, ensure_ascii=False, indent=2),
                       file_name="listing.json", mime="application/json", key=dl_key)

# ---------- UI ----------
st.markdown(f"<div class='hero'><h1>{t['title']}</h1><p>{t['caption']}</p></div>", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state["history"] = []

# ---------- left panel (opens via the arrow top-left): saved listings ----------
with st.sidebar:
    st.markdown(f"### {a.get('history_title', 'Your listings')}")
    if st.session_state["history"]:
        if st.button(a.get("clear", "Clear"), key="clear_hist", use_container_width=True):
            st.session_state["history"] = []
            st.rerun()
        for _i, _it in enumerate(st.session_state["history"]):
            _ttl = _it.get("label") or (_it["out"].get("seo_title", "") or "")[:38]
            with st.expander(_ttl or f"#{_i + 1}"):
                st.code(_it["out"].get("seo_title", ""), language=None)
                st.write(_it["out"].get("description", ""))
                for _b in _it["out"].get("bullet_points", []):
                    st.markdown(f"- {_b}")
                st.code(", ".join(_it["out"].get("tags", [])), language=None)
                st.code(_it["out"].get("meta_description", ""), language=None)
    else:
        st.caption(a.get("history_empty", ""))

_g1, _g2 = st.columns([3, 1])
with _g1:
    st.markdown(f"<div style='padding-top:8px;color:#94a3b8'>{a['hi'].format(name=st.session_state.get('sb_name',''))}</div>",
                unsafe_allow_html=True)
with _g2:
    if st.button(a["logout"], key="logout_btn", use_container_width=True):
        for _k in ("sb_token", "sb_name", "used", "sb_rt"):
            st.session_state.pop(_k, None)
        _ls_set("sb_rt", "")
        st.rerun()

remaining = SESSION_LIMIT - st.session_state["used"]
_next_reset = (st.session_state.get("period_start") or time.time()) + 86400
_secs_left = max(0, int(_next_reset - time.time()))
_rh, _rm = _secs_left // 3600, (_secs_left % 3600) // 60
_usage_txt = t["gens_left"].format(n=max(remaining, 0), lim=SESSION_LIMIT)
_usage_txt += " " + a.get("resets_in", "· resets in {h}h {m}m").format(h=_rh, m=_rm)
st.markdown(f"<div class='usage'>{_usage_txt}</div>", unsafe_allow_html=True)
st.markdown(t["intro"])

# --- product: photo / URL are the headline feature, shown up front ---
st.markdown(f"<div class='section'>{t['sec_product']}</div>", unsafe_allow_html=True)
photo = st.file_uploader(t["photo"], type=["jpg", "jpeg", "png"])
if photo:
    st.image(photo, width=220)
url = st.text_input(t["url"], placeholder=t["url_ph"])

st.caption(t["or_manual"])
name = st.text_input(t["product_name"], placeholder=t["product_name_ph"])
features = st.text_area(t["features"], height=100, placeholder=t["features_ph"])

st.markdown(f"<div class='section'>{t['sec_settings']}</div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    marketplace = st.selectbox(t["marketplace"], MARKETPLACES)
with c2:
    language = st.selectbox(t["out_lang"],
                            ["English", "Spanish", "French", "German", "Portuguese",
                             "Italian", "Dutch", "Polish", "Chinese (Simplified)",
                             "Japanese", "Arabic", "Russian", "Ukrainian", "Turkish"])

# --- optional / advanced ---
with st.expander(t["adv"]):
    category = st.text_input(t["category"], placeholder=t["category_ph"])
    tone_values = ["Professional", "Friendly", "Luxury", "Playful", "Minimalist"]
    tone = st.selectbox(t["tone"], tone_values, format_func=lambda v: t["tones"].get(v, v))
    keywords = st.text_input(t["keywords"], placeholder=t["keywords_ph"])
    st.markdown("---")
    st.markdown(f"**{t.get('bulk', T['en']['bulk'])}**")
    bulk = st.file_uploader(t.get("bulk", T["en"]["bulk"]), type=["jpg", "jpeg", "png"],
                            accept_multiple_files=True, key="bulk", label_visibility="collapsed")
    st.caption(t.get("bulk_hint", T["en"]["bulk_hint"]))
    if bulk:
        st.image([b for b in bulk[:10]], width=90)

st.write("")
if st.button(t["generate"], type="primary", use_container_width=True):
    imgs = list(bulk) if bulk else ([photo] if photo else [])
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
    elif not imgs and not ctx.strip() and not name.strip():
        st.warning(t["warn_input"])
    else:
        # One generation per photo (up to the remaining free limit); or a single text/URL job.
        if imgs:
            jobs = imgs[:remaining]
            if len(imgs) > remaining:
                st.warning(t.get("warn_partial", T["en"]["warn_partial"]).format(done=remaining, total=len(imgs)))
        else:
            jobs = [None]
        st.success(t["done"])
        for idx, ph in enumerate(jobs, start=1):
            img_bytes = ph.getvalue() if ph else None
            img_mime = ph.type if ph else None
            label = ph.name if ph else ""
            with st.spinner(t["spinner"]):
                try:
                    out = generate(
                        build_prompt(name, ctx, category, marketplace, tone, keywords,
                                     has_image=bool(img_bytes), language=language),
                        image_bytes=img_bytes, image_mime=img_mime,
                    )
                    st.session_state["used"] += 1
                    sb_set_usage(st.session_state["used"], st.session_state.get("period_start") or time.time())
                    st.session_state["history"].insert(0, {"label": label, "out": out})
                    render_result(out, t, dl_key=f"dl_{idx}", label=label)
                except json.JSONDecodeError:
                    st.error(t["err_format"])
                except Exception as e:
                    st.error(str(e))
