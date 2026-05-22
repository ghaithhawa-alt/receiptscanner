# -*- coding: utf-8 -*-
import http.server
import json
import urllib.request
import urllib.error
import os, sys, random, string, time
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
PORT             = int(os.environ.get("PORT", 8080))
API_KEY          = os.environ.get("ANTHROPIC_API_KEY", "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")
SMTP_EMAIL       = os.environ.get("SMTP_EMAIL", "ghaithhawa90@gmail.com")
SMTP_PASS        = os.environ.get("SMTP_PASS",  "yihwkgwnttdyemns")
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "ghaithhawa90@gmail.com")
APP_URL          = os.environ.get("APP_URL", "http://localhost:8080")
DB_FILE          = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "database.json")))
# ============================================================

def resource_path(p):
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / p
    return Path(__file__).parent / p

# =============================================
#  DATENBANK
# =============================================
def db_load():
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"users": {}, "sessions": {}, "codes": {}, "scans": []}

def db_save(db):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user(email):
    return db_load()["users"].get(email.lower())

def save_user(user):
    db = db_load()
    db["users"][user["email"].lower()] = user
    db_save(db)

def get_session(token):
    db = db_load()
    email = db["sessions"].get(token)
    if not email: return None
    return db["users"].get(email.lower())

def create_session(email):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
    db = db_load()
    db["sessions"][token] = email.lower()
    db_save(db)
    return token

def save_scan(scan_data):
    db = db_load()
    db["scans"].append(scan_data)
    db_save(db)

# =============================================
#  EMAIL
# =============================================
def send_code(email, name=""):
    code = ''.join(random.choices(string.digits, k=6))
    db   = db_load()
    db["codes"][email.lower()] = {
        "code":    code,
        "expires": (datetime.now() + timedelta(minutes=10)).isoformat()
    }
    db_save(db)

    sent = False
    resend_key = os.environ.get("RESEND_API_KEY", "")

    if resend_key:
        try:
            html = f"""<div style="font-family:Arial;max-width:480px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;">
<div style="background:#22c55e;padding:24px;text-align:center;"><h1 style="color:#000;margin:0;">ReceiptScanner</h1></div>
<div style="padding:32px;">
<p>Hallo{' '+name if name else ''},</p>
<p style="margin:16px 0;">Dein Login-Code:</p>
<div style="background:#f0fdf4;border:2px solid #22c55e;border-radius:10px;padding:20px;text-align:center;">
<span style="font-size:2.5rem;font-weight:900;letter-spacing:8px;color:#16a34a;">{code}</span>
</div>
<p style="color:#888;font-size:.85rem;margin-top:16px;">Gueltig fuer 10 Minuten.</p>
</div></div>"""

            body = json.dumps({
                "from":    "ReceiptScanner <onboarding@resend.dev>",
                "to":      [email],
                "subject": f"Dein Code: {code}",
                "html":    html
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=body,
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            sent = True
            print(f"[EMAIL] Gesendet -> {email}")
        except Exception as e:
            print(f"[EMAIL FEHLER] {e}")
    else:
        print("[EMAIL] Kein RESEND_API_KEY!")

    print(f"\n{'='*40}\n  CODE: {code}  ({email})\n{'='*40}\n")
    return code, sent

def verify_code(email, code):
    db    = db_load()
    entry = db["codes"].get(email.lower())
    if not entry: return False
    if entry["code"] != code: return False
    if datetime.now() > datetime.fromisoformat(entry["expires"]): return False
    del db["codes"][email.lower()]
    db_save(db)
    return True

# =============================================
#  SUPERADMIN
# =============================================
def ensure_superadmin():
    db    = db_load()
    email = SUPERADMIN_EMAIL.lower()
    sa    = db["users"].get(email)
    if not sa:
        db["users"][email] = {
            "email": email, "name": "Superadmin", "role": "superadmin",
            "active": True, "approved": True, "quota": 99999,
            "used": 0, "price": 0, "created": datetime.now().isoformat(),
        }
        db_save(db)
        print(f"[INIT] Superadmin: {SUPERADMIN_EMAIL}")
    else:
        changed = False
        if sa.get("role") != "superadmin": sa["role"] = "superadmin"; changed = True
        if not sa.get("approved"):         sa["approved"] = True;      changed = True
        if sa.get("quota", 0) < 99999:     sa["quota"] = 99999;        changed = True
        if not sa.get("active"):           sa["active"] = True;        changed = True
        if changed:
            db["users"][email] = sa
            db_save(db)

# =============================================
#  HTTP HANDLER
# =============================================
class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def get_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            t = auth[7:].strip()
            return t if t else None
        return None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._serve(resource_path("app") / "index.html")
        elif path in ("/admin", "/admin/", "/admin/index.html"):
            self._serve(resource_path("admin") / "index.html")
        elif path in ("/login", "/login.html"):
            self._serve(resource_path("app") / "login.html")
        elif path == "/favicon.ico":
            self.send_response(204); self.end_headers()
        else:
            self.send_error(404)

    def _serve(self, fpath):
        fpath = Path(fpath)
        if not fpath.exists():
            self.send_error(404, fpath.name); return
        content = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if   path == "/api/auth/send-code":    self._send_code()
            elif path == "/api/auth/verify":        self._verify()
            elif path == "/api/auth/me":            self._me()
            elif path == "/api/scan":               self._scan()
            elif path == "/api/admin/users":        self._admin_users()
            elif path == "/api/admin/approve":      self._approve()
            elif path == "/api/admin/update-user":  self._update_user()
            elif path == "/api/admin/delete-user":  self._delete_user()
            elif path == "/api/admin/promote":      self._promote()
            elif path == "/api/admin/stats":        self._stats()
            elif path == "/api/admin/scans":        self._admin_scans()
            else: self.send_error(404)
        except Exception as e:
            print(f"[FEHLER] {path}: {e}")
            self.send_json({"error": str(e)}, 500)

    def _send_code(self):
        data  = self.read_body()
        email = data.get("email", "").strip().lower()
        name  = data.get("name", "").strip()
        if not email or "@" not in email:
            self.send_json({"error": "Ungueltige Email"}, 400); return

        user   = get_user(email)
        is_new = user is None

        if is_new:
            if not name:
                self.send_json({"need_name": True}); return
            user = {
                "email": email, "name": name, "role": "nutzer",
                "active": True, "approved": False, "quota": 0,
                "used": 0, "price": 0, "created": datetime.now().isoformat(),
            }
            if email == SUPERADMIN_EMAIL.lower():
                user["role"] = "superadmin"; user["approved"] = True; user["quota"] = 99999
            save_user(user)

        code, sent = send_code(email, user.get("name", ""))
        self.send_json({"ok": True, "is_new": is_new, "sent": sent,
                        "msg": "Code gesendet!" if sent else f"Code: {code}"})

    def _verify(self):
        data  = self.read_body()
        email = data.get("email", "").strip().lower()
        code  = data.get("code", "").strip()
        if not verify_code(email, code):
            self.send_json({"error": "Falscher oder abgelaufener Code"}, 401); return
        user = get_user(email)
        if not user:
            self.send_json({"error": "Nutzer nicht gefunden"}, 404); return
        if not user.get("approved"):
            self.send_json({"error": "Konto wartet auf Admin-Freigabe."}, 403); return
        if not user.get("active"):
            self.send_json({"error": "Konto deaktiviert."}, 403); return
        token = create_session(email)
        self.send_json({"ok": True, "token": token, "user": {k:v for k,v in user.items()}})

    def _me(self):
        user = get_session(self.get_token() or "")
        if not user:
            self.send_json({"error": "Nicht eingeloggt"}, 401); return
        self.send_json({"ok": True, "user": user})

    def _scan(self):
        user = get_session(self.get_token() or "")
        if not user:
            self.send_json({"error": "Nicht eingeloggt"}, 401); return
        user = get_user(user["email"]) or user
        if not user.get("approved"):
            self.send_json({"error": "Konto nicht genehmigt"}, 403); return
        if user.get("role") not in ("superadmin", "admin"):
            if user.get("used", 0) >= user.get("quota", 0):
                self.send_json({"error": "Monatliches Limit erreicht"}, 429); return

        data = self.read_body()
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": "claude-opus-4-5", "max_tokens": 600,
                    "messages": data.get("messages", [])
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = resp.read()

            user["used"] = user.get("used", 0) + 1
            save_user(user)
            save_scan({"email": user["email"], "name": user.get("name",""),
                       "datum": datetime.now().strftime("%d.%m.%Y"),
                       "filename": data.get("filename",""), "ts": datetime.now().isoformat()})

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(result)

        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            print(f"[CLAUDE FEHLER] {e.code}: {err[:200]}")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err.encode("utf-8"))

    def _check_admin(self):
        user = get_session(self.get_token() or "")
        if not user: return None, "Nicht eingeloggt"
        if user.get("role") not in ("admin","superadmin"): return None, "Kein Admin"
        return user, None

    def _admin_users(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        self.send_json({"ok": True, "users": list(db_load()["users"].values())})

    def _approve(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data   = self.read_body()
        email  = data.get("email","").lower()
        target = get_user(email)
        if not target: self.send_json({"error": "Nicht gefunden"}, 404); return
        target["approved"] = True
        target["quota"]    = int(data.get("quota", 500))
        target["price"]    = float(data.get("price", 9.99))
        if data.get("name"): target["name"] = data["name"]
        if data.get("role") and user.get("role") == "superadmin": target["role"] = data["role"]
        save_user(target)
        self.send_json({"ok": True})

    def _update_user(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data   = self.read_body()
        email  = data.get("email","").lower()
        target = get_user(email)
        if not target: self.send_json({"error": "Nicht gefunden"}, 404); return
        for k in ("name","quota","price","active"):
            if k in data: target[k] = data[k]
        save_user(target)
        self.send_json({"ok": True})

    def _delete_user(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data  = self.read_body()
        email = data.get("email","").lower()
        db    = db_load()
        db["users"].pop(email, None)
        db_save(db)
        self.send_json({"ok": True})

    def _promote(self):
        user = get_session(self.get_token() or "")
        if not user or user.get("role") != "superadmin":
            self.send_json({"error": "Nur Superadmin"}, 403); return
        data   = self.read_body()
        target = get_user(data.get("email","").lower())
        if not target: self.send_json({"error": "Nicht gefunden"}, 404); return
        target["role"] = data.get("role","nutzer")
        save_user(target)
        self.send_json({"ok": True})

    def _stats(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        db    = db_load()
        users = list(db["users"].values())
        now_m = datetime.now().strftime(".%m.%Y")
        self.send_json({
            "ok": True,
            "total_users":    len(users),
            "active_users":   sum(1 for u in users if u.get("active") and u.get("approved")),
            "pending_users":  sum(1 for u in users if not u.get("approved")),
            "monthly_scans":  len([s for s in db["scans"] if s.get("datum","").endswith(now_m)]),
            "monthly_revenue": round(sum(u.get("price",0) for u in users if u.get("active") and u.get("approved")), 2),
        })

    def _admin_scans(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        self.send_json({"ok": True, "scans": db_load()["scans"][-100:]})


def main():
    ensure_superadmin()

    base = Path(__file__).parent
    print(f"\n{'='*45}")
    print(f"  ReceiptScanner Server")
    print(f"  Ordner: {base}")
    print(f"{'='*45}")

    for f in [base/"app"/"login.html", base/"app"/"index.html", base/"admin"/"index.html"]:
        print(f"  {'[OK]' if f.exists() else '[FEHLT]'} {f.relative_to(base)}")

    print(f"\n  Nutzer:  http://localhost:{PORT}/login")
    print(f"  Admin:   http://localhost:{PORT}/admin")
    print(f"{'='*45}\n")

    import threading, webbrowser
    def open_b():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}/login")
    threading.Thread(target=open_b, daemon=True).start()

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Gestoppt")

if __name__ == "__main__":
    main()
