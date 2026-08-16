# build: redeploy trigger 2026-08-15
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
def _load_gemini_keys():
    """Collect all Gemini API keys from secrets: GEMINI_API_KEY, GEMINI_API_KEY_2, _3...
    Multiple keys = load-balancing across users + automatic failover when one hits
    its free-tier limit. Put each key on a separate Google account/project so the
    free quotas actually add up."""
    keys = []
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4"):
        v = (st.secrets.get(name, "") or "").strip()
        if v and not v.startswith("PASTE"):
            keys.append(v)
    return keys

API_KEYS = _load_gemini_keys()
API_KEY = API_KEYS[0] if API_KEYS else ""  # used only for the "is any key configured?" check
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MODEL = st.secrets.get("GEMINI_MODEL", "gemini-flash-latest")
# Free tier: 10 generations per visitor session (will become per-account after auth).
SESSION_LIMIT = min(int(st.secrets.get("SESSION_LIMIT", "10")), 10)
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

try:
    _page_icon = "logo.jpg"  # tab favicon = SellyAI logo
except Exception:
    _page_icon = "🛍️"
st.set_page_config(page_title="SellyAI", page_icon=_page_icon,
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
/* Only size the sidebar when it's actually open; collapsed = full width for centered content */
section[data-testid="stSidebar"] {background: #0d1117;}
section[data-testid="stSidebar"][aria-expanded="true"] {width: 300px !important; min-width: 300px !important;}
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
/* Clear hamburger button (top-left) to open the "my listings" side panel */
[data-testid="stSidebarCollapsedControl"] {display:flex !important; visibility:visible !important; opacity:1 !important; top:10px !important; left:10px !important;}
[data-testid="stSidebarCollapsedControl"] button {background:#161b26 !important; border:1px solid #2b3448 !important; border-radius:10px !important; width:auto !important; padding:6px 12px !important;}
[data-testid="stSidebarCollapsedControl"] button svg {display:none !important;}
[data-testid="stSidebarCollapsedControl"] button::before {content:"\2630"; font-size:20px; line-height:1; color:#e8ebf2;}
[data-testid="stSidebarCollapsedControl"] button:hover {border-color:#4f7cff !important;}
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

# Browser persistence ("remember me") via a tiny JS bridge (localStorage <-> URL ?rt=).
# No external package, so it can never break the build; every call is wrapped so a
# failure just degrades to session-only login (no crash).
import streamlit.components.v1 as _components

def _persist_write_rt(token):
    if not token:
        return
    try:
        _components.html(
            "<script>try{window.parent.localStorage.setItem('pdg_rt',"
            + json.dumps(str(token)) + ");}catch(e){}</script>", height=0)
    except Exception:
        pass

def _persist_clear_rt():
    try:
        _components.html(
            "<script>try{window.parent.localStorage.removeItem('pdg_rt');}catch(e){}</script>", height=0)
    except Exception:
        pass

def _persist_bootstrap():
    # If a saved token is in localStorage but not yet in the URL, add it as ?rt= and reload.
    try:
        _components.html(
            """
            <script>
            try{
              var W = window.parent, rt = null;
              try { rt = W.localStorage.getItem('pdg_rt'); } catch(e){}
              var href = W.location.href;
              if (rt && href.indexOf('rt=') === -1) {
                var sep = (href.indexOf('?') === -1) ? '?' : '&';
                W.location.replace(href.split('#')[0] + sep + 'rt=' + encodeURIComponent(rt));
              }
            }catch(e){}
            </script>
            """, height=0)
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
    "es": {
        "title": "Crea una cuenta para usar el generador",
        "sub": "Inicia sesión o regístrate — obtienes 10 generaciones gratis.",
        "signin": "Iniciar sesión", "register": "Registrarse",
        "email": "Correo electrónico", "password": "Contraseña", "first": "Nombre", "last": "Apellido",
        "signin_btn": "Iniciar sesión", "register_btn": "Crear cuenta",
        "err_login": "Correo o contraseña incorrectos.",
        "err_register": "No se pudo registrar. Prueba otro correo o una contraseña más segura (mín. 6 caracteres).",
        "check_email": "Cuenta creada. Confirma tu correo y luego inicia sesión.",
        "logout": "Cerrar sesión", "hi": "Hola, {name}",
        "account": "Cuenta", "history_title": "Tus anuncios", "clear": "Borrar anuncios",
        "history_empty": "Aquí aparecerán tus anuncios generados.",
        "resets_in": "· las generaciones gratis se renuevan en {h}h {m}m",
        "forgot": "¿Olvidaste tu contraseña?",
        "recover_btn": "Enviar enlace de restablecimiento",
        "recover_sent": "Si existe una cuenta con ese correo, se ha enviado un enlace para restablecer la contraseña. Revisa tu bandeja (y spam).",
        "set_new_pw": "Establece una nueva contraseña",
        "new_pw_ph": "Nueva contraseña (mín. 6 caracteres)",
        "update_pw_btn": "Actualizar contraseña",
        "pw_updated": "Contraseña actualizada. Ya puedes iniciar sesión con tu nueva contraseña.",
        "pw_update_err": "No se pudo actualizar la contraseña. El enlace pudo haber caducado — solicita uno nuevo.",
    },
    "fr": {
        "title": "Créez un compte pour utiliser le générateur",
        "sub": "Connectez-vous ou inscrivez-vous — 10 générations gratuites.",
        "signin": "Connexion", "register": "Inscription",
        "email": "E-mail", "password": "Mot de passe", "first": "Prénom", "last": "Nom",
        "signin_btn": "Se connecter", "register_btn": "Créer un compte",
        "err_login": "E-mail ou mot de passe incorrect.",
        "err_register": "Inscription impossible. Essayez un autre e-mail ou un mot de passe plus fort (min. 6 caractères).",
        "check_email": "Compte créé. Confirmez votre e-mail, puis connectez-vous.",
        "logout": "Déconnexion", "hi": "Bonjour, {name}",
        "account": "Compte", "history_title": "Vos annonces", "clear": "Effacer les annonces",
        "history_empty": "Vos annonces générées apparaîtront ici.",
        "resets_in": "· générations gratuites réinitialisées dans {h}h {m}m",
        "forgot": "Mot de passe oublié ?",
        "recover_btn": "Envoyer le lien de réinitialisation",
        "recover_sent": "Si un compte existe pour cet e-mail, un lien de réinitialisation a été envoyé. Vérifiez votre boîte (et les spams).",
        "set_new_pw": "Définir un nouveau mot de passe",
        "new_pw_ph": "Nouveau mot de passe (min. 6 caractères)",
        "update_pw_btn": "Mettre à jour le mot de passe",
        "pw_updated": "Mot de passe mis à jour. Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.",
        "pw_update_err": "Impossible de mettre à jour le mot de passe. Le lien a peut-être expiré — demandez-en un nouveau.",
    },
    "de": {
        "title": "Erstellen Sie ein Konto, um den Generator zu nutzen",
        "sub": "Melden Sie sich an oder registrieren Sie sich — 10 kostenlose Generierungen.",
        "signin": "Anmelden", "register": "Registrieren",
        "email": "E-Mail", "password": "Passwort", "first": "Vorname", "last": "Nachname",
        "signin_btn": "Anmelden", "register_btn": "Konto erstellen",
        "err_login": "Falsche E-Mail oder falsches Passwort.",
        "err_register": "Registrierung fehlgeschlagen. Versuchen Sie eine andere E-Mail oder ein stärkeres Passwort (mind. 6 Zeichen).",
        "check_email": "Konto erstellt. Bitte bestätigen Sie Ihre E-Mail und melden Sie sich an.",
        "logout": "Abmelden", "hi": "Hallo, {name}",
        "account": "Konto", "history_title": "Ihre Listings", "clear": "Listings löschen",
        "history_empty": "Ihre generierten Listings erscheinen hier.",
        "resets_in": "· kostenlose Generierungen werden in {h}h {m}m zurückgesetzt",
        "forgot": "Passwort vergessen?",
        "recover_btn": "Link zum Zurücksetzen senden",
        "recover_sent": "Falls ein Konto mit dieser E-Mail existiert, wurde ein Link zum Zurücksetzen gesendet. Prüfen Sie Ihren Posteingang (und Spam).",
        "set_new_pw": "Neues Passwort festlegen",
        "new_pw_ph": "Neues Passwort (mind. 6 Zeichen)",
        "update_pw_btn": "Passwort aktualisieren",
        "pw_updated": "Passwort aktualisiert. Sie können sich jetzt mit Ihrem neuen Passwort anmelden.",
        "pw_update_err": "Passwort konnte nicht aktualisiert werden. Der Link ist möglicherweise abgelaufen — fordern Sie einen neuen an.",
    },
    "it": {
        "title": "Crea un account per usare il generatore",
        "sub": "Accedi o registrati — ottieni 10 generazioni gratuite.",
        "signin": "Accedi", "register": "Registrati",
        "email": "Email", "password": "Password", "first": "Nome", "last": "Cognome",
        "signin_btn": "Accedi", "register_btn": "Crea account",
        "err_login": "Email o password errati.",
        "err_register": "Registrazione non riuscita. Prova un'altra email o una password più sicura (min. 6 caratteri).",
        "check_email": "Account creato. Conferma la tua email, poi accedi.",
        "logout": "Esci", "hi": "Ciao, {name}",
        "account": "Account", "history_title": "I tuoi annunci", "clear": "Cancella annunci",
        "history_empty": "Qui appariranno i tuoi annunci generati.",
        "resets_in": "· le generazioni gratuite si rinnovano tra {h}h {m}m",
        "forgot": "Password dimenticata?",
        "recover_btn": "Invia link di reimpostazione",
        "recover_sent": "Se esiste un account con questa email, è stato inviato un link per reimpostare la password. Controlla la posta (e lo spam).",
        "set_new_pw": "Imposta una nuova password",
        "new_pw_ph": "Nuova password (min. 6 caratteri)",
        "update_pw_btn": "Aggiorna password",
        "pw_updated": "Password aggiornata. Ora puoi accedere con la nuova password.",
        "pw_update_err": "Impossibile aggiornare la password. Il link potrebbe essere scaduto — richiedine uno nuovo.",
    },
    "pt": {
        "title": "Crie uma conta para usar o gerador",
        "sub": "Entre ou registre-se — você recebe 10 gerações grátis.",
        "signin": "Entrar", "register": "Registrar",
        "email": "E-mail", "password": "Senha", "first": "Nome", "last": "Sobrenome",
        "signin_btn": "Entrar", "register_btn": "Criar conta",
        "err_login": "E-mail ou senha incorretos.",
        "err_register": "Não foi possível registrar. Tente outro e-mail ou uma senha mais forte (mín. 6 caracteres).",
        "check_email": "Conta criada. Confirme seu e-mail e depois entre.",
        "logout": "Sair", "hi": "Olá, {name}",
        "account": "Conta", "history_title": "Seus anúncios", "clear": "Limpar anúncios",
        "history_empty": "Seus anúncios gerados aparecerão aqui.",
        "resets_in": "· gerações grátis renovam em {h}h {m}m",
        "forgot": "Esqueceu sua senha?",
        "recover_btn": "Enviar link de redefinição",
        "recover_sent": "Se existir uma conta com esse e-mail, um link de redefinição de senha foi enviado. Verifique sua caixa de entrada (e spam).",
        "set_new_pw": "Defina uma nova senha",
        "new_pw_ph": "Nova senha (mín. 6 caracteres)",
        "update_pw_btn": "Atualizar senha",
        "pw_updated": "Senha atualizada. Agora você pode entrar com sua nova senha.",
        "pw_update_err": "Não foi possível atualizar a senha. O link pode ter expirado — solicite um novo.",
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
        _persist_write_rt(rt)

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

# Public URL of THIS Streamlit app — the reset link must land here (not the
# marketing wrapper page) so the in-app "set new password" form can run.
APP_PUBLIC_URL = "https://pdg-app-gz6vrgsebbhha2schirhtx.streamlit.app"

def sb_recover(email):
    # Sends a Supabase password-reset email. redirect_to sends the user back to
    # this app after clicking the link. Returns 200 regardless of whether the
    # email exists (anti-enumeration), so we always show the same neutral message.
    return requests.post(f"{SUPABASE_URL}/auth/v1/recover",
                         params={"redirect_to": APP_PUBLIC_URL},
                         headers=SB_HEADERS, json={"email": email}, timeout=30)

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
    # Cache the recovery access token in session_state: the token_hash is SINGLE-USE,
    # so we must NOT re-verify it on every rerun (that would fail and drop to login).
    _rec_at = st.session_state.get("recovery_token") or st.query_params.get("recovery_at")
    # Reliable flow: the reset link carries ?token_hash=...&type=recovery. Exchange
    # it for a session once, then keep it for the rest of the flow.
    _th = st.query_params.get("token_hash")
    if not _rec_at and _th and st.query_params.get("type") == "recovery":
        try:
            _vr = requests.post(f"{SUPABASE_URL}/auth/v1/verify", headers=SB_HEADERS,
                                json={"type": "recovery", "token_hash": _th}, timeout=30)
            if _vr.status_code == 200 and _vr.json().get("access_token"):
                _rec_at = _vr.json()["access_token"]
                st.session_state["recovery_token"] = _rec_at
        except Exception:
            pass
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
                        st.session_state["recovery_token"] = None
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
# Merge over English so any missing translation key falls back to English (never crashes).
_lang_code = UI_LANGS[ui_lang_name]
t = {**T["en"], **T.get(_lang_code, {})}

# ---------- auth gate (Supabase: email + password) ----------
a = {**AUTH["en"], **AUTH.get(_lang_code, {})}

# Remember me: restore a saved session from the browser before showing the login screen.
if not st.session_state.get("sb_token"):
    if st.session_state.pop("just_logged_out", False):
        _persist_clear_rt()  # user logged out: wipe saved token, skip auto-restore this run
        try:
            del st.query_params["rt"]
        except Exception:
            pass
    else:
        _persist_bootstrap()  # moves a saved token from localStorage into ?rt=
        _rt = st.session_state.get("sb_rt") or st.query_params.get("rt")
        if _rt:
            try:
                _rr = sb_refresh(_rt)
                if _rr.status_code == 200 and _rr.json().get("access_token"):
                    _sb_apply_session(_rr.json())
                    try:
                        del st.query_params["rt"]  # don't leave the token in the URL
                    except Exception:
                        pass
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
    "Shopify": (
        "SHOPIFY — a direct-to-consumer BRAND store. VOICE: warm, confident, benefit-led brand storytelling that builds desire while staying truthful. "
        "TITLE: brand-friendly and clean, primary keyword included, ~50-70 chars, Title Case, no marketplace clutter. "
        "DESCRIPTION: open with a short hook sentence, then 120-180 words in 1-2 scannable paragraphs about how the product fits the buyer's life (not a spec dump). "
        "BULLETS: 4-6 lifestyle benefits, each a short phrase (what the buyer gains), not raw specs. "
        "TAGS: 8-12 SEO collection/search keywords a shopper would actually type. "
        "Build desire only through concrete, real benefits — never through invented quality or hype adjectives."
    ),
    "Amazon": (
        "AMAZON — a high-intent search marketplace; strict and compliant. VOICE: clear, factual, product-first, zero fluff. "
        "TITLE: front-load the MAIN keyword, then key attributes (brand, product type, colour, material, size, quantity), Title Case, ~150-200 chars, no promo words, no '!'. "
        "DESCRIPTION: one factual paragraph covering the core attributes and use. "
        "BULLETS: EXACTLY 5, each starting with a CAPITALIZED benefit label then ' — ', e.g. 'DURABLE BUILD — ...'; each conveys one concrete attribute/benefit. "
        "TAGS: backend search terms as single words / short synonyms, no competitor brand names, no repetition. "
        "COMPLIANT: no unverifiable claims, no shipping/seller info, no 'best / #1 / must-have'."
    ),
    "Etsy": (
        "ETSY — handmade, vintage and craft buyers who value story and uniqueness. VOICE: warm, personal, artisan; mention who it's for and gifting occasions when it genuinely fits. "
        "TITLE: a long, descriptive long-tail phrase real buyers search (~110-140 chars), leading with the most-searched terms (item + style + material + occasion). "
        "DESCRIPTION: friendly, slightly personal story — what it is, materials, craftsmanship/finish, dimensions if provided, and gifting/use ideas. "
        "BULLETS: 4-6 points highlighting craftsmanship, materials, size and use. "
        "TAGS: EXACTLY 13, each a multi-word long-tail phrase (keep each <=20 chars) mixing material, style, occasion, recipient and aesthetic — no single generic words, no unrelated brands."
    ),
    "eBay": (
        "EBAY — buyers search by brand, model and exact specs; trust and accuracy win. VOICE: factual, informative, no fluff. "
        "TITLE: <=80 chars PACKED with the terms buyers search — brand + model + product type + key specs + size/colour. "
        "DESCRIPTION: spec-first and honest — condition, exact dimensions/size, material, colour, compatibility / what's included, and any visible flaws. "
        "BULLETS: 5-7 concrete spec points, no marketing language. "
        "TAGS: brand + model + product type + key specs. Trustworthy tone throughout."
    ),
    "Walmart": (
        "WALMART — mainstream, everyday-value, family-friendly shoppers; compliant and plain. VOICE: simple, practical, no hype or superlatives. "
        "TITLE: short and keyword-optimized — brand + product type + key attribute (+ size/colour), Title Case. "
        "DESCRIPTION: concise factual paragraph on what it is, practical use and value. "
        "BULLETS: 4-6 points on practical use, value for money and clear specs. "
        "TAGS: 8-12 practical search terms. Avoid 'best / premium / amazing'."
    ),
    "Vinted": (
        "VINTED — peer-to-peer second-hand fashion (EU). VOICE: casual, honest, first-person, like a real person selling their own item ('Selling my...'). "
        "TITLE: brand + item + size + colour, short and natural. "
        "DESCRIPTION: short and personal; state the essentials up front — brand, size, exact MATERIAL/FABRIC (only if known), colour, CONDITION, measurements and fit — and be upfront about any flaws. "
        "BULLETS: 3-6 concrete facts (brand, size, material, colour, condition, measurements). "
        "TAGS: brand + garment type + style. NO corporate marketing language, NO invented measurements, NO authenticity claims unless explicitly known."
    ),
    "AliExpress": (
        "ALIEXPRESS — global budget marketplace, many non-native-English buyers. VOICE: plain, simple, very keyword-dense and spec-focused; short clear sentences. "
        "TITLE: long, stuffed with attributes and synonyms buyers might search (product type + material + colour + size + use + synonyms). "
        "DESCRIPTION: simple sentences covering specs and use-cases. "
        "BULLETS: 5-6 concrete spec / use-case points in plain wording. "
        "TAGS: many (10-15) long-tail terms and synonyms."
    ),
}
MARKETPLACES = ["Shopify", "Amazon", "Etsy", "eBay", "Walmart", "Vinted", "AliExpress"]

def build_prompt(name, features, category, marketplace, tone, keywords, has_image=False, language="English"):
    hint = MARKET_HINTS.get(marketplace, "")
    img_line = ("A photo of the product is attached. Silently analyze the image "
                "(product type; brand/logo only if clearly legible; colours; visible design "
                "details; visible materials/texture; and any visible signs of wear or damage) "
                "and base the listing on what you can actually see. Use the text fields below "
                "as extra context.\n\n") if has_image else ""
    return f"""You are an expert marketplace listing copywriter and product-image analyst.

Your task is NOT to write generic marketing copy and NOT to make the product sound artificially impressive. Create a natural, accurate, useful marketplace listing that a real seller would actually post on platforms such as Vinted, eBay, Amazon, Depop, Etsy and Facebook Marketplace. It must feel human-written, practical and trustworthy.

CORE PRINCIPLE — write a MARKETPLACE LISTING, not a generic product description. Help the buyer quickly understand: what the item is, what it looks like, its visible characteristics, brand (only if clearly visible), colour, style/type, material (only if known or reasonably identifiable), size (only if visible or provided), condition (only from visible evidence or provided info), and notable visible details. Goal = accuracy + usefulness + natural language. Do NOT make every product sound luxurious, premium, revolutionary or exceptional.

1. NEVER INVENT INFORMATION (most important). Only state info that is clearly visible in the image, explicitly provided, or identifiable with very high confidence. NEVER invent: exact material, composition percentages, measurements, size, brand, model, country of manufacture, technical specs, certifications, waterproofing, durability, insulation, quality level, authenticity, original price, age, or condition details that cannot be seen. If something cannot be determined, leave it out. Never turn uncertainty into a fact.

2. NO FAKE MARKETING LANGUAGE. Avoid adjectives whose only purpose is to make it sound better; describe concrete characteristics instead. e.g. "Black handbag with a structured shape, two top handles and a front zip pocket." not "Premium, stylish and elegant leather handbag."

3. WRITE LIKE A REAL SELLER — natural, straightforward. Do not sound like an ad agency, a luxury brand, an SEO generator, an AI assistant or a catalog. Prefer "Black Nike hoodie with a small chest logo and a front kangaroo pocket." over "Elevate your everyday wardrobe with this timeless premium hoodie."

4. FOCUS ON INFO THAT HELPS THE BUYER — depending on the product, consider: type, brand, colour, pattern, style, visible design details, closures, pockets, straps, sleeves, collar, neckline, sole, heel, hardware, logos, prints, visible materials/texture, and any visible wear, stains, scratches, tears or missing parts. Do not force every category into every listing — only mention relevant details.

5. CONDITION MUST BE HONEST. Never automatically label an item as new / like new / excellent / perfect / unused unless explicitly provided or clearly supported. If a visible flaw exists, mention it. If condition cannot be determined, do not invent it.

6. IMAGE ANALYSIS (silent, before writing). Identify: the product; visible brand/logo; colour(s); design/features; visible materials/texture; visible wear or damage; readable label text; and what cannot be confidently determined. If ambiguous, DO NOT guess (e.g. if it looks like leather with no reliable evidence, write "smooth finish", not "leather"; if a logo is not clearly legible, do not name the brand).

7. SEO — BUT NATURALLY. Use words a buyer would actually search, woven in naturally (e.g. "Black oversized hoodie with a zip front, hood and kangaroo pockets"). Never keyword-stuff, never repeat a word just for SEO, never add unrelated brands or brands merely associated with the style.

8. VINTED-SPECIFIC. Prioritise clear item identification, brand, colour, size (if known), style/type, material (if known), measurements (if provided), condition and visible flaws. No unrelated brands, no hashtags unless requested, no fake measurements, no authenticity claims unless explicitly known.

9. AMAZON-SPECIFIC. Clear, factual, product-focused. Avoid promotional claims, seller/contact info, URLs, excessive exclamation marks, keyword stuffing, unsubstantiated claims, shipping info, artificial urgency, and "best / number one / must-have" claims.

10. PLATFORM ADAPTATION. Fully adapt the voice, title length, description structure, number of bullets and tag style to the target marketplace using the platform playbook provided below. Shopify, Amazon, Etsy, eBay, Walmart, Vinted and AliExpress each read very differently — the same product must produce a listing that looks native to the selected marketplace and clearly different from how you'd write it for another. If the platform is unclear, use a neutral marketplace style that works across platforms.

11. TITLE. Make it clear and searchable: [Brand] + [Product Type] + [Key Characteristic] + [Colour/Style] + [Size if known], e.g. "Zara Oversized Linen-Style Blazer Beige Size M". No promotional adjectives, no "!!!".

12. Do NOT describe the photo itself ("in the image...", "the photo shows...", "as seen in the picture..."). Write directly about the product.

13. NO DISCLAIMERS in the output ("I cannot determine...", "it is difficult to tell...", "based on the image...", "I am an AI..."). Uncertainty should change WHAT you write, not appear as a disclaimer.

14. HUMAN QUALITY CHECK before returning: did I invent anything? use generic marketing language? exaggerate? repeat myself? state a material/brand/size/condition without sufficient evidence? add irrelevant keywords or brands? Does every sentence give useful info and match the actual product? Rewrite before returning if any answer is problematic.

{img_line}Target marketplace: {marketplace}
Platform playbook for {marketplace} — follow it FULLY so the listing reads unmistakably like a top {marketplace} listing (its voice, title length, description structure, number of bullets and tag style) and clearly different from another marketplace. The honesty / no-invention / no-hype rules above ALWAYS override any persuasive tone it suggests: {hint}
Output language: {language}
Requested tone: {tone}
Product name: {name or "(only what is actually visible or provided — do not invent a name)"}
Category: {category or "(not specified)"}
Known details provided by the seller: {features or "(none provided beyond the photo)"}
Focus keywords to weave in naturally, only if genuinely relevant (optional): {keywords or "(none provided)"}

CRITICAL LANGUAGE RULE: Write EVERY field (seo_title, description, bullet_points, tags, meta_description) entirely in {language}. Every single word of the output must be in {language}. Do NOT use English unless {language} is "English". Adapt any provided keywords naturally into {language}.

Return STRICT JSON ONLY (no extra text, no explanations, no mention of these instructions), matching exactly this schema:
{{
  "seo_title": "clear searchable title per rule 11, <= 80 chars, in {language}",
  "description": "natural, factual, seller-style listing following all rules above, in {language}",
  "bullet_points": ["concrete factual selling point in {language}", "...", "... (how many + what style depends on the marketplace guidance above — Amazon: EXACTLY 5 benefit-labelled bullets; eBay/Vinted/Walmart: concrete specs; otherwise 3-6 useful points)"],
  "tags": ["relevant natural search term in {language}", "... (Etsy: EXACTLY 13 multi-word long-tail phrases; otherwise 6-12 relevant terms; lowercase; no '#' unless requested; no unrelated brands)"],
  "meta_description": "<= 155 chars, factual summary, in {language}"
}}"""

def fetch_url_text(url: str) -> str:
    import re
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", r.text)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:6000]


# Known-good fallbacks are appended so generation still works even if a preview
# model name changes.
GEN_MODELS = [MODEL, "gemini-flash-latest", "gemini-3.6-flash", "gemini-3.5-flash"]
# De-dupe while preserving order.
GEN_MODELS = list(dict.fromkeys([m for m in GEN_MODELS if m]))

def generate(prompt: str, image_bytes=None, image_mime=None) -> dict:
    import base64, time, random
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
    # Load-balance across all configured keys (random start), and fail over to the
    # next key when one is rate-limited / quota-exhausted (429).
    keys = [k for k in (API_KEYS or [API_KEY]) if k]
    random.shuffle(keys)
    last_err = "no api key"
    for key in keys:
        switch_key = False
        for m in GEN_MODELS:
            if switch_key:
                break
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
            for attempt in range(2):
                try:
                    r = requests.post(url, params={"key": key}, json=body, timeout=60)
                except Exception as e:
                    last_err = str(e)
                    time.sleep(1.0 * (attempt + 1))
                    continue
                if r.status_code == 200:
                    try:
                        data = r.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(text)
                    except Exception:
                        last_err = "unexpected response format"
                        time.sleep(0.8)
                        continue  # bad/partial response — retry
                if r.status_code == 429:
                    last_err = f"429: {r.text[:120]}"
                    switch_key = True  # this key is exhausted → try the next key
                    break
                if r.status_code in (500, 502, 503):
                    last_err = f"{r.status_code}"
                    time.sleep(1.2 * (attempt + 1))  # transient overload — retry
                    continue
                last_err = f"API {r.status_code}: {r.text[:120]}"
                break  # e.g. unknown model — try the next model
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

# ---------- saved listings panel (in-page ☰ button; works inside the embedded iframe) ----------
_hist = st.session_state["history"]
_hist_label = "☰ " + a.get("history_title", "Your listings") + (f" ({len(_hist)})" if _hist else "")
if st.button(_hist_label, key="hist_toggle"):
    st.session_state["show_hist"] = not st.session_state.get("show_hist", False)
if st.session_state.get("show_hist"):
    if _hist:
        if st.button(a.get("clear", "Clear"), key="clear_hist"):
            st.session_state["history"] = []
            st.rerun()
        for _i, _it in enumerate(_hist):
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
        st.session_state["just_logged_out"] = True
        _persist_clear_rt()
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
        _status = st.empty()  # "ready" message goes here — filled ONLY after generation succeeds
        _any_ok = False
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
                    _any_ok = True
                except json.JSONDecodeError:
                    st.error(t["err_format"])
                except Exception as e:
                    st.error(str(e))
        if _any_ok:
            _status.success(t["done"])
