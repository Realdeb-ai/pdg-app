"""
SellyAI — Product Description Generator (Streamlit)
Fixes: blank screen (full UI restored) + persistent login via browser cookie.
Generation uses Gemini if GEMINI_API_KEY is set in Secrets, otherwise a built-in
template engine so the app ALWAYS produces output.
"""
import time
import json
import requests
import streamlit as st

# ---------- Page config ----------
st.set_page_config(
    page_title="SellyAI — Product Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Style (safe: does NOT remove page body) ----------
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"], section[data-testid="stSidebar"] {
        background-color: #0e1117 !important;
    }
    #MainMenu { visibility: hidden !important; }
    section[data-testid="stSidebar"] { border-right: 1px solid #232a38 !important; }
    .block-container { max-width: 880px !important; padding-top: 1.5rem !important; }
    .result-card {
        background: #161b26; border: 1px solid #232a38; border-radius: 14px;
        padding: 18px 20px; margin-top: 12px;
    }
    .brand { font-weight: 800; font-size: 30px; }
    .brand span {
        background: linear-gradient(90deg,#4f7cff,#8a5cf6);
        -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Optional cookie manager (persistent login) ----------
# Wrapped so that if the component ever fails, the app STILL renders.
cookies = None
try:
    import extra_streamlit_components as stx

    # NOTE: must NOT be wrapped in st.cache_* — CookieManager runs a widget
    # command internally, which Streamlit forbids inside cached functions.
    cookies = stx.CookieManager(key="pdg_cookies")
except Exception:
    cookies = None


def read_user_cookie():
    if cookies is None:
        return None
    try:
        return cookies.get("pdg_user")
    except Exception:
        return None


def write_user_cookie(email):
    if cookies is None:
        return
    try:
        cookies.set("pdg_user", email, max_age=60 * 60 * 24 * 90, key="set_user")
    except Exception:
        pass


def clear_user_cookie():
    if cookies is None:
        return
    try:
        cookies.delete("pdg_user", key="del_user")
    except Exception:
        pass


# ---------- Session state ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "history" not in st.session_state:
    st.session_state.history = []
if "used" not in st.session_state:
    st.session_state.used = 0

SESSION_LIMIT = int(st.secrets.get("SESSION_LIMIT", 25)) if hasattr(st, "secrets") else 25

# Auto-login from cookie
if st.session_state.user is None:
    saved = read_user_cookie()
    if saved:
        st.session_state.user = saved


# ---------- Generation ----------
def generate_with_gemini(name, features, tone, marketplace):
    key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    if not key or key.startswith("PASTE"):
        return None
    model = st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash")
    if model in ("gemini-3.5-flash",):  # fix placeholder name from example
        model = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    prompt = (
        f"You are an expert e-commerce copywriter. Write a high-converting, SEO-optimized "
        f"product listing for {marketplace}.\n"
        f"Product name: {name}\nKey features: {features}\nTone: {tone}\n\n"
        f"Return in this exact structure:\n"
        f"SEO TITLE: <one line, max 70 chars>\n"
        f"BULLETS:\n- <benefit 1>\n- <benefit 2>\n- <benefit 3>\n- <benefit 4>\n- <benefit 5>\n"
        f"DESCRIPTION: <2 short persuasive paragraphs>\n"
        f"META: <meta description max 155 chars>\n"
        f"TAGS: <10 comma-separated keywords>"
    )
    try:
        r = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}),
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def generate_template(name, features, tone, marketplace):
    feats = [f.strip() for f in features.replace("\n", ",").split(",") if f.strip()]
    if not feats:
        feats = ["premium quality", "durable design", "great value"]
    bullets = "\n".join(f"- {f[0].upper() + f[1:]}" for f in feats[:5])
    while bullets.count("\n") < 4:
        bullets += "\n- Backed by our satisfaction guarantee"
    tags = ", ".join(dict.fromkeys(
        [name.lower()] + [f.lower() for f in feats] +
        [marketplace.lower(), "best seller", "gift idea", "2026"]
    ).keys())[:180]
    return (
        f"SEO TITLE: {name} — {feats[0].title()} | {marketplace} Best Seller\n\n"
        f"BULLETS:\n{bullets}\n\n"
        f"DESCRIPTION:\n"
        f"Meet the {name}, designed for people who want {feats[0]} without compromise. "
        f"Every detail is crafted to deliver {', '.join(feats[:3])}, so you get real value from day one.\n\n"
        f"Whether it's for daily use or a thoughtful gift, the {name} stands out on {marketplace}. "
        f"Order today and see the difference {tone.lower()} quality makes.\n\n"
        f"META: {name}: {feats[0]}, {feats[1] if len(feats) > 1 else 'top quality'}. Shop now on {marketplace}.\n\n"
        f"TAGS: {tags}"
    )


# ============================================================
#  AUTH GATE
# ============================================================
st.markdown('<div class="brand">Selly<span>AI</span></div>', unsafe_allow_html=True)
st.caption("SEO product descriptions in seconds.")

if not st.session_state.user:
    st.subheader("Sign in / Register")
    st.write("Enter your email to start. We'll remember you on this device — no re-registering.")
    with st.form("register"):
        email = st.text_input("Email")
        submitted = st.form_submit_button("Continue →")
    if submitted:
        if email and "@" in email:
            st.session_state.user = email.strip().lower()
            write_user_cookie(st.session_state.user)
            st.success("Welcome! Loading your generator…")
            time.sleep(0.6)
            st.rerun()
        else:
            st.warning("Please enter a valid email.")
    st.stop()

# ============================================================
#  MAIN APP (logged in)
# ============================================================
with st.sidebar:
    st.markdown(f"**Signed in:** {st.session_state.user}")
    st.caption(f"Used this session: {st.session_state.used}/{SESSION_LIMIT}")
    if st.button("Log out"):
        clear_user_cookie()
        st.session_state.user = None
        st.rerun()
    st.divider()
    st.header("History")
    if st.session_state.history:
        for i, item in enumerate(reversed(st.session_state.history), 1):
            with st.expander(f"{i}. {item['name']}"):
                st.code(item["out"], language=None)
    else:
        st.caption("Your generations will appear here.")

st.subheader("Generate a product description")
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Product name", placeholder="e.g. Bamboo Cutting Board")
    marketplace = st.selectbox("Marketplace", ["Amazon", "Etsy", "Shopify", "eBay", "Website"])
with col2:
    tone = st.selectbox("Tone", ["Professional", "Friendly", "Luxury", "Playful", "Minimalist"])
    features = st.text_area("Key features (comma or line separated)",
                            placeholder="eco-friendly, non-slip, easy to clean")

if st.button("✨ Generate", type="primary"):
    if not name or not features:
        st.warning("Fill in product name and features.")
    elif st.session_state.used >= SESSION_LIMIT:
        st.error("Session limit reached. Refresh or come back later.")
    else:
        with st.spinner("Writing your listing…"):
            out = generate_with_gemini(name, features, tone, marketplace)
            if out is None:
                out = generate_template(name, features, tone, marketplace)
        st.session_state.history.append({"name": name, "out": out})
        st.session_state.used += 1
        st.markdown('<div class="result-card">', unsafe_allow_html=True)
        st.markdown("#### Result")
        st.code(out, language=None)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Tip: click the copy icon in the top-right of the box above.")
