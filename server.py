# -*- coding: utf-8 -*-
"""
ReceiptScanner Server v2.0
==========================
- Landing Page mit Abo-System
- Passwort-Auth + Email-Code Bestätigung
- Superadmin / Admin / Nutzer Rollen
- Resend Email
"""
import http.server, json, urllib.request, urllib.error
import os, sys, random, string, time, hashlib
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except: pass

# ============================================================
PORT             = int(os.environ.get("PORT", 8080))
API_KEY          = os.environ.get("ANTHROPIC_API_KEY", "")
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "ghaithhawa90@gmail.com")
APP_URL          = os.environ.get("APP_URL", "http://localhost:8080")
DB_FILE          = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "database.json")))
RESEND_KEY       = os.environ.get("RESEND_API_KEY", "")

PLANS = {
    "starter": {"name": "Starter",    "price_month": 5.99,  "price_year": 57.99,  "quota": 500},
    "pro":     {"name": "Pro",         "price_month": 11.99, "price_year": 115.99, "quota": 1000},
    "business":{"name": "Business",   "price_month": 89.99, "price_year": 869.99, "quota": 999999},
}
# ============================================================

def rp(p):
    if hasattr(sys, '_MEIPASS'): return Path(sys._MEIPASS) / p
    return Path(__file__).parent / p

# ── DB ──────────────────────────────────────────────────────
def db_load():
    if DB_FILE.exists():
        try: return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except: pass
    return {"users":{}, "sessions":{}, "codes":{}, "scans":[], "payments":[]}

def db_save(db):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user(email):   return db_load()["users"].get(email.lower())
def save_user(u):
    db = db_load(); db["users"][u["email"].lower()] = u; db_save(db)

def get_session(tok):
    db = db_load(); email = db["sessions"].get(tok)
    if not email: return None
    return db["users"].get(email.lower())

def create_session(email):
    tok = ''.join(random.choices(string.ascii_letters+string.digits, k=48))
    db = db_load(); db["sessions"][tok] = email.lower(); db_save(db)
    return tok

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

# ── EMAIL ────────────────────────────────────────────────────
def send_email(to, subject, html):
    if not RESEND_KEY:
        print(f"[EMAIL] Kein Key! Inhalt: {subject}")
        return False
    try:
        body = json.dumps({"from":"ReceiptScanner <onboarding@resend.dev>",
                           "to":[to], "subject":subject, "html":html}).encode()
        req = urllib.request.Request("https://api.resend.com/emails", data=body,
            headers={"Authorization":f"Bearer {RESEND_KEY}","Content-Type":"application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r: r.read()
        print(f"[EMAIL] Gesendet -> {to}")
        return True
    except Exception as e:
        print(f"[EMAIL FEHLER] {e}"); return False

def send_code_email(email, code, name=""):
    html = f"""<div style="font-family:Arial;max-width:480px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;">
<div style="background:#22c55e;padding:24px;text-align:center;"><h1 style="color:#000;margin:0;font-size:1.4rem;">ReceiptScanner</h1></div>
<div style="padding:32px;">
<p style="color:#333;">Hallo{' '+name if name else ''},</p>
<p style="color:#555;margin:16px 0;">Dein Bestätigungs-Code:</p>
<div style="background:#f0fdf4;border:2px solid #22c55e;border-radius:10px;padding:24px;text-align:center;">
<span style="font-size:2.8rem;font-weight:900;letter-spacing:10px;color:#16a34a;">{code}</span></div>
<p style="color:#888;font-size:.85rem;margin-top:16px;">Gültig für 10 Minuten. Bitte nicht weitergeben.</p>
</div></div>"""
    return send_email(email, f"Dein ReceiptScanner Code: {code}", html)

def gen_code(email):
    code = ''.join(random.choices(string.digits, k=6))
    db = db_load()
    db["codes"][email.lower()] = {"code":code, "expires":(datetime.now()+timedelta(minutes=10)).isoformat()}
    db_save(db)
    print(f"\n{'='*40}\n  CODE: {code}  ({email})\n{'='*40}\n")
    return code

def verify_code(email, code):
    db = db_load(); e = db["codes"].get(email.lower())
    if not e or e["code"]!=code: return False
    if datetime.now() > datetime.fromisoformat(e["expires"]): return False
    del db["codes"][email.lower()]; db_save(db); return True

# ── SUPERADMIN ───────────────────────────────────────────────
def ensure_superadmin():
    db = db_load(); em = SUPERADMIN_EMAIL.lower()
    sa = db["users"].get(em)
    if not sa:
        db["users"][em] = {"email":em,"name":"Superadmin","role":"superadmin",
            "active":True,"approved":True,"quota":999999,"used":0,
            "plan":"business","plan_type":"month","plan_expires":"",
            "created":datetime.now().isoformat(),"pw_hash":""}
        db_save(db); print(f"[INIT] Superadmin: {em}")
    else:
        upd = False
        for k,v in [("role","superadmin"),("approved",True),("active",True)]:
            if sa.get(k)!=v: sa[k]=v; upd=True
        if sa.get("quota",0)<999999: sa["quota"]=999999; upd=True
        if upd: db["users"][em]=sa; db_save(db)

# ── HANDLER ──────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, f, *a): print(f"[{self.address_string()}] {f%a}")

    def send_json(self, data, code=200):
        b = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(b)

    def rb(self):
        n = int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n))

    def tok(self):
        a = self.headers.get("Authorization","")
        return a[7:].strip() if a.startswith("Bearer ") else None

    def do_OPTIONS(self):
        self.send_response(200)
        for h,v in [("Access-Control-Allow-Origin","*"),
                    ("Access-Control-Allow-Methods","POST,GET,OPTIONS"),
                    ("Access-Control-Allow-Headers","Content-Type,Authorization")]:
            self.send_header(h,v)
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        routes = {
            "/":          rp("app")/"index.html",
            "/index.html":rp("app")/"index.html",
            "/app":       rp("app")/"index.html",
            "/login":     rp("app")/"login.html",
            "/login.html":rp("app")/"login.html",
            "/landing":   rp("app")/"landing.html",
            "/admin":     rp("admin")/"index.html",
            "/admin/":    rp("admin")/"index.html",
        }
        if p == "/favicon.ico": self.send_response(204); self.end_headers(); return
        if p in routes: self._serve(routes[p]); return
        # Serve root as landing for unauthenticated
        self._serve(rp("app")/"landing.html")

    def _serve(self, fp):
        fp = Path(fp)
        if not fp.exists(): self.send_error(404, fp.name); return
        c = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(c)))
        self.end_headers(); self.wfile.write(c)

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            m = {
                "/api/auth/register":      self._register,
                "/api/auth/verify-email":  self._verify_email,
                "/api/auth/login":         self._login,
                "/api/auth/me":            self._me,
                "/api/scan":               self._scan,
                "/api/admin/users":        self._admin_users,
                "/api/admin/approve":      self._approve,
                "/api/admin/update-user":  self._update_user,
                "/api/admin/delete-user":  self._delete_user,
                "/api/admin/promote":      self._promote,
                "/api/admin/stats":        self._stats,
                "/api/admin/scans":        self._admin_scans,
                "/api/admin/send-mail":    self._admin_send_mail,
                "/api/plans":              self._get_plans,
                "/api/checkout":           self._checkout,
            }.get(p)
            if m: m()
            else: self.send_error(404)
        except Exception as e:
            print(f"[ERR] {p}: {e}")
            self.send_json({"error":str(e)}, 500)

    # ── AUTH ─────────────────────────────────────────────────
    def _register(self):
        d = self.rb()
        email = d.get("email","").strip().lower()
        name  = d.get("name","").strip()
        pw    = d.get("password","").strip()
        if not email or "@" not in email:
            self.send_json({"error":"Ungültige Email"},400); return
        if not name:
            self.send_json({"error":"Name erforderlich"},400); return
        if not pw or len(pw)<6:
            self.send_json({"error":"Passwort min. 6 Zeichen"},400); return
        if get_user(email):
            self.send_json({"error":"Email bereits registriert"},409); return
        code = gen_code(email)
        sent = send_code_email(email, code, name)
        # Temp speichern bis Verifizierung
        db = db_load()
        db["codes"][email+"_reg"] = {"name":name,"pw_hash":hash_pw(pw),"ts":datetime.now().isoformat()}
        db_save(db)
        self.send_json({"ok":True,"sent":sent,"msg":"Code gesendet!" if sent else f"Code: {code}"})

    def _verify_email(self):
        d = self.rb()
        email = d.get("email","").strip().lower()
        code  = d.get("code","").strip()
        if not verify_code(email, code):
            self.send_json({"error":"Falscher oder abgelaufener Code"},401); return
        db   = db_load()
        reg  = db["codes"].get(email+"_reg", {})
        name = reg.get("name", email.split("@")[0])
        pw_h = reg.get("pw_hash","")
        db["codes"].pop(email+"_reg", None)
        db_save(db)
        is_sa = email == SUPERADMIN_EMAIL.lower()
        user = {
            "email":email,"name":name,"role":"superadmin" if is_sa else "nutzer",
            "active":True,"approved":is_sa,"quota":999999 if is_sa else 0,
            "used":0,"price":0,"plan":"","plan_type":"month","plan_expires":"",
            "created":datetime.now().isoformat(),"pw_hash":pw_h,
        }
        save_user(user)
        if is_sa:
            tok = create_session(email)
            self.send_json({"ok":True,"token":tok,"user":self._safe(user)})
        else:
            self.send_json({"ok":True,"pending":True,"msg":"Registrierung abgeschlossen! Du kannst dich jetzt anmelden."})

    def _login(self):
        d = self.rb()
        email = d.get("email","").strip().lower()
        pw    = d.get("password","").strip()
        user  = get_user(email)
        if not user:
            self.send_json({"error":"Email nicht gefunden"},404); return
        if user.get("pw_hash") and user["pw_hash"] != hash_pw(pw):
            self.send_json({"error":"Falsches Passwort"},401); return
        if not user.get("approved") and user.get("role") not in ("admin","superadmin"):
            self.send_json({"error":"Konto wartet auf Freigabe oder Abo-Aktivierung"},403); return
        if not user.get("active"):
            self.send_json({"error":"Konto deaktiviert"},403); return
        tok = create_session(email)
        self.send_json({"ok":True,"token":tok,"user":self._safe(user)})

    def _me(self):
        u = get_session(self.tok() or "")
        if not u: self.send_json({"error":"Nicht eingeloggt"},401); return
        self.send_json({"ok":True,"user":self._safe(u)})

    def _safe(self, u):
        return {k:v for k,v in u.items() if k != "pw_hash"}

    # ── SCAN ─────────────────────────────────────────────────
    def _scan(self):
        u = get_session(self.tok() or "")
        if not u: self.send_json({"error":"Nicht eingeloggt"},401); return
        u = get_user(u["email"]) or u
        if not u.get("approved") and u.get("role") not in ("admin","superadmin"):
            self.send_json({"error":"Kein aktives Abo"},403); return
        if u.get("role") not in ("superadmin","admin"):
            if u.get("used",0) >= u.get("quota",0):
                self.send_json({"error":"Monatliches Limit erreicht"},429); return
        d = self.rb()
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({"model":"claude-opus-4-5","max_tokens":600,
                                 "messages":d.get("messages",[])}).encode(),
                headers={"Content-Type":"application/json","x-api-key":API_KEY,
                         "anthropic-version":"2023-06-01"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r: result = r.read()
            u["used"] = u.get("used",0)+1; save_user(u)
            db = db_load()
            db["scans"].append({"email":u["email"],"name":u.get("name",""),
                "datum":datetime.now().strftime("%d.%m.%Y"),
                "filename":d.get("filename",""),"ts":datetime.now().isoformat()})
            db_save(db)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers(); self.wfile.write(result)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8","replace")
            print(f"[CLAUDE] {e.code}: {err[:200]}")
            self.send_response(e.code)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers(); self.wfile.write(err.encode())

    # ── PLANS / CHECKOUT ────────────────────────────────────
    def _get_plans(self):
        self.send_json({"ok":True,"plans":PLANS})

    def _checkout(self):
        # Simuliert Zahlung - in Produktion: Stripe/PayPal Webhook
        u = get_session(self.tok() or "")
        if not u: self.send_json({"error":"Nicht eingeloggt"},401); return
        d     = self.rb()
        plan  = d.get("plan","starter")
        ptype = d.get("type","month")  # month or year
        if plan not in PLANS:
            self.send_json({"error":"Unbekannter Plan"},400); return
        p = PLANS[plan]
        days  = 365 if ptype=="year" else 30
        exp   = (datetime.now()+timedelta(days=days)).strftime("%d.%m.%Y")
        user  = get_user(u["email"])
        user["plan"]         = plan
        user["plan_type"]    = ptype
        user["plan_expires"] = exp
        user["quota"]        = p["quota"]
        user["approved"]     = True
        user["price"]        = p["price_year"] if ptype=="year" else p["price_month"]
        save_user(user)
        db = db_load()
        db["payments"].append({"email":u["email"],"plan":plan,"type":ptype,
            "amount":user["price"],"ts":datetime.now().isoformat()})
        db_save(db)
        self.send_json({"ok":True,"expires":exp,"quota":p["quota"]})

    # ── ADMIN ────────────────────────────────────────────────
    def _chkadm(self):
        u = get_session(self.tok() or "")
        if not u: return None,"Nicht eingeloggt"
        if u.get("role") not in ("admin","superadmin"): return None,"Kein Admin"
        return u, None

    def _admin_users(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        self.send_json({"ok":True,"users":list(db_load()["users"].values())})

    def _approve(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        d = self.rb(); em = d.get("email","").lower()
        t = get_user(em)
        if not t: self.send_json({"error":"Nicht gefunden"},404); return
        t["approved"] = True
        t["quota"]    = int(d.get("quota",500))
        t["price"]    = float(d.get("price",5.99))
        if d.get("plan"): t["plan"] = d["plan"]
        if d.get("role") and u.get("role")=="superadmin": t["role"]=d["role"]
        save_user(t); self.send_json({"ok":True})

    def _update_user(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        d = self.rb(); t = get_user(d.get("email","").lower())
        if not t: self.send_json({"error":"Nicht gefunden"},404); return
        for k in ("name","quota","price","active","plan","plan_expires"):
            if k in d: t[k]=d[k]
        save_user(t); self.send_json({"ok":True})

    def _delete_user(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        d = self.rb(); db = db_load()
        db["users"].pop(d.get("email","").lower(), None); db_save(db)
        self.send_json({"ok":True})

    def _promote(self):
        u = get_session(self.tok() or "")
        if not u or u.get("role")!="superadmin":
            self.send_json({"error":"Nur Superadmin"},403); return
        d = self.rb(); t = get_user(d.get("email","").lower())
        if not t: self.send_json({"error":"Nicht gefunden"},404); return
        t["role"]=d.get("role","nutzer"); save_user(t)
        self.send_json({"ok":True})

    def _stats(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        db = db_load(); users = list(db["users"].values())
        nm = datetime.now().strftime(".%m.%Y")
        rev = sum(u.get("price",0) for u in users if u.get("active") and u.get("approved"))
        self.send_json({"ok":True,
            "total_users":   len(users),
            "active_users":  sum(1 for u in users if u.get("active") and u.get("approved")),
            "pending_users": sum(1 for u in users if not u.get("approved")),
            "monthly_scans": len([s for s in db["scans"] if s.get("datum","").endswith(nm)]),
            "monthly_revenue": round(rev,2),
            "total_payments": len(db.get("payments",[])),
        })

    def _admin_scans(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        self.send_json({"ok":True,"scans":db_load()["scans"][-200:]})

    def _admin_send_mail(self):
        u,e = self._chkadm()
        if e: self.send_json({"error":e},403); return
        d = self.rb()
        to  = d.get("to","")
        sub = d.get("subject","Nachricht von ReceiptScanner")
        msg = d.get("message","")
        html = f"""<div style="font-family:Arial;max-width:600px;margin:0 auto;">
<div style="background:#22c55e;padding:20px;text-align:center;">
<h1 style="color:#000;margin:0;">ReceiptScanner</h1></div>
<div style="padding:24px;"><p>{msg}</p></div></div>"""
        ok = send_email(to, sub, html)
        self.send_json({"ok":ok})


def main():
    ensure_superadmin()
    base = Path(__file__).parent
    print(f"\n{'='*50}\n  ReceiptScanner v2.0\n{'='*50}")
    for f in ["app/landing.html","app/login.html","app/index.html","admin/index.html"]:
        fp = base/f
        print(f"  {'✓' if fp.exists() else '✗ FEHLT'} {f}")
    print(f"\n  URL: http://localhost:{PORT}")
    print(f"  Admin: http://localhost:{PORT}/admin")
    print(f"{'='*50}\n")

    import threading, webbrowser
    threading.Thread(target=lambda: (time.sleep(1.2),
        webbrowser.open(f"http://localhost:{PORT}")), daemon=True).start()

    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
