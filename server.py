# -*- coding: utf-8 -*-
"""
ReceiptScanner Server - Komplett System
======================================
- Email-Authentifizierung mit Code
- Nutzer-Verwaltung (Admin genehmigt)
- Multi-Upload & Scan
- Rollen: superadmin, admin, nutzer
"""

import http.server
import json
import urllib.request
import urllib.error
import os, sys, random, string, hashlib, time
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
#  KONFIGURATION - Werte kommen von Railway Umgebungsvariablen
# ============================================================
PORT        = int(os.environ.get("PORT", 8080))
API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "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")
SMTP_HOST   = "smtp.gmail.com"
SMTP_PORT   = 587
SMTP_EMAIL  = os.environ.get("SMTP_EMAIL", "ghaithhawa90@gmail.com")
SMTP_PASS   = os.environ.get("SMTP_PASS",  "iwjzahbjnniryotp")
APP_NAME    = "ReceiptScanner"
APP_URL     = os.environ.get("APP_URL", "http://localhost:8080")
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "ghaithhawa90@gmail.com")
# ============================================================
# ============================================================

DB_FILE = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "database.json")))

def resource_path(p):
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / p
    return Path(__file__).parent / p

# =============================================
#  DATENBANK (JSON)
# =============================================
def db_load():
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "users":    {},   # email -> user object
        "sessions": {},   # token -> email
        "codes":    {},   # email -> {code, expires}
        "scans":    [],   # alle scans
    }

def db_save(db):
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user(email):
    db = db_load()
    return db["users"].get(email.lower())

def save_user(user):
    db = db_load()
    db["users"][user["email"].lower()] = user
    db_save(db)

def get_session(token):
    db = db_load()
    email = db["sessions"].get(token)
    if not email: return None
    # Immer frischen User laden
    user = db["users"].get(email.lower())
    return user

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
#  EMAIL CODE SENDEN
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
    if SMTP_EMAIL and SMTP_PASS:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            anrede = f"Hallo {name}," if name else "Hallo,"

            html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;">
  <div style="background:#22c55e;padding:24px;text-align:center;">
    <h1 style="color:#000;margin:0;font-size:1.4rem;">ReceiptScanner</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:1rem;">{anrede}</p>
    <p style="color:#555;margin-bottom:24px;">Dein Login-Code lautet:</p>
    <div style="background:#f0fdf4;border:2px solid #22c55e;border-radius:10px;
                padding:20px;text-align:center;margin-bottom:24px;">
      <span style="font-size:2.5rem;font-weight:900;letter-spacing:8px;color:#16a34a;">
        {code}
      </span>
    </div>
    <p style="color:#888;font-size:.85rem;">
      Dieser Code ist <strong>10 Minuten</strong> gueltig.<br>
      Falls du dich nicht angemeldet hast, ignoriere diese Email.
    </p>
  </div>
  <div style="background:#f9f9f9;padding:16px;text-align:center;">
    <p style="color:#aaa;font-size:.75rem;margin:0;">ReceiptScanner &mdash; Intelligenter Belegscanner</p>
  </div>
</div>
</body>
</html>"""

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Dein ReceiptScanner Code: {code}"
            msg["From"]    = f"ReceiptScanner <{SMTP_EMAIL}>"
            msg["To"]      = email
            msg.attach(MIMEText(f"Dein Code: {code} (10 Minuten gueltig)", "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.ehlo()
                s.starttls()
                s.login(SMTP_EMAIL, SMTP_PASS)
                s.send_message(msg)
            sent = True
            print(f"[EMAIL] Code {code} -> {email}")
        except Exception as e:
            print(f"[EMAIL FEHLER] {e}")

    print(f"\n{'='*40}")
    print(f"  CODE fuer {email}: {code}")
    print(f"{'='*40}\n")
    return code, sent

def test_email():
    """Testet Email beim Start."""
    if not SMTP_EMAIL or not SMTP_PASS:
        print("[EMAIL] Nicht konfiguriert - Code nur im Terminal")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText("ReceiptScanner Email-Test erfolgreich!")
        msg["Subject"] = "ReceiptScanner - Email Test"
        msg["From"]    = SMTP_EMAIL
        msg["To"]      = SMTP_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASS)
            s.send_message(msg)
        print(f"[EMAIL] OK - Emails werden gesendet!")
    except Exception as e:
        print(f"[EMAIL FEHLER] {e}")
        print(f"[EMAIL] Code wird nur im Terminal angezeigt")

def verify_code(email, code):
    db  = db_load()
    entry = db["codes"].get(email.lower())
    if not entry: return False
    if entry["code"] != code: return False
    if datetime.now() > datetime.fromisoformat(entry["expires"]): return False
    del db["codes"][email.lower()]
    db_save(db)
    return True

# =============================================
#  INIT SUPERADMIN
# =============================================
def ensure_superadmin():
    db = db_load()
    email = SUPERADMIN_EMAIL.lower()
    sa = db["users"].get(email)
    if not sa:
        db["users"][email] = {
            "email":    email,
            "name":     "Superadmin",
            "role":     "superadmin",
            "active":   True,
            "approved": True,
            "quota":    99999,
            "used":     0,
            "price":    0,
            "created":  datetime.now().isoformat(),
        }
        db_save(db)
        print(f"[INIT] Superadmin erstellt: {SUPERADMIN_EMAIL}")
    else:
        # Sicherstellen dass Superadmin immer korrekte Werte hat
        changed = False
        if sa.get("role") != "superadmin": sa["role"] = "superadmin"; changed = True
        if not sa.get("approved"):         sa["approved"] = True;      changed = True
        if sa.get("quota", 0) < 99999:    sa["quota"] = 99999;        changed = True
        if not sa.get("active"):           sa["active"] = True;        changed = True
        if changed:
            db["users"][email] = sa
            db_save(db)
            print(f"[INIT] Superadmin aktualisiert")

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
            self._serve_file(resource_path("app") / "index.html")
        elif path in ("/admin", "/admin/", "/admin/index.html"):
            self._serve_file(resource_path("admin") / "index.html")
        elif path in ("/login", "/login.html", "/app/login.html"):
            self._serve_file(resource_path("app") / "login.html")
        elif path == "/favicon.ico":
            self.send_response(204); self.end_headers()
        else:
            self.send_error(404)

    def _serve_file(self, fpath):
        fpath = Path(fpath)
        if not fpath.exists():
            self.send_error(404, f"Nicht gefunden: {fpath.name}")
            return
        content = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = self.path.split("?")[0]

        try:
            if path == "/api/auth/send-code":
                self._handle_send_code()
            elif path == "/api/auth/verify":
                self._handle_verify()
            elif path == "/api/auth/me":
                self._handle_me()
            elif path == "/api/scan":
                self._handle_scan()
            elif path == "/api/admin/users":
                self._handle_admin_users()
            elif path == "/api/admin/approve":
                self._handle_approve()
            elif path == "/api/admin/update-user":
                self._handle_update_user()
            elif path == "/api/admin/delete-user":
                self._handle_delete_user()
            elif path == "/api/admin/promote":
                self._handle_promote()
            elif path == "/api/admin/stats":
                self._handle_stats()
            elif path == "/api/admin/scans":
                self._handle_admin_scans()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[FEHLER] {path}: {e}")
            self.send_json({"error": str(e)}, 500)

    # --- AUTH ---
    def _handle_send_code(self):
        data  = self.read_body()
        email = data.get("email", "").strip().lower()
        name  = data.get("name", "").strip()
        if not email or "@" not in email:
            self.send_json({"error": "Ungueltige Email"}, 400); return

        # Pruefen ob Nutzer existiert
        user = get_user(email)
        is_new = user is None

        if is_new:
            # Neuer Nutzer -> registrieren
            if not name:
                self.send_json({"need_name": True,
                                "msg": "Bitte Name eingeben"})
                return
            user = {
                "email":    email,
                "name":     name,
                "role":     "nutzer",
                "active":   True,
                "approved": False,
                "quota":    0,
                "used":     0,
                "price":    0,
                "created":  datetime.now().isoformat(),
            }
            if email == SUPERADMIN_EMAIL.lower():
                user["role"]     = "superadmin"
                user["approved"] = True
                user["quota"]    = 99999
            save_user(user)

        code, sent = send_code(email, user.get("name",""))
        self.send_json({
            "ok":     True,
            "is_new": is_new,
            "sent":   sent,
            "msg":    "Code gesendet!" if sent else f"Code (nur Terminal): {code}"
        })

    def _handle_verify(self):
        data  = self.read_body()
        email = data.get("email", "").strip().lower()
        code  = data.get("code", "").strip()

        if not verify_code(email, code):
            self.send_json({"error": "Falscher oder abgelaufener Code"}, 401); return

        user = get_user(email)
        if not user:
            self.send_json({"error": "Nutzer nicht gefunden"}, 404); return

        if not user.get("approved"):
            self.send_json({"error": "Konto wurde noch nicht genehmigt. Bitte warte auf Admin-Freigabe."}, 403); return

        if not user.get("active"):
            self.send_json({"error": "Konto ist deaktiviert."}, 403); return

        token = create_session(email)
        self.send_json({"ok": True, "token": token, "user": self._safe_user(user)})

    def _handle_me(self):
        token = self.get_token()
        user  = get_session(token) if token else None
        if not user:
            self.send_json({"error": "Nicht eingeloggt"}, 401); return
        self.send_json({"ok": True, "user": self._safe_user(user)})

    def _safe_user(self, u):
        return {k: v for k, v in u.items() if k != "password"}

    # --- SCAN ---
    def _handle_scan(self):
        token = self.get_token()
        user  = get_session(token) if token else None
        if not user:
            self.send_json({"error": "Nicht eingeloggt"}, 401); return

        # Immer frischen User aus DB laden (aktuellste Quota)
        user = get_user(user["email"]) or user

        if not user.get("approved"):
            self.send_json({"error": "Konto nicht genehmigt"}, 403); return

        # Superadmin hat immer unlimitierten Zugang
        if user.get("role") not in ("superadmin", "admin"):
            if user.get("used", 0) >= user.get("quota", 0):
                self.send_json({"error": "Monatliches Limit erreicht"}, 429); return

        data = self.read_body()
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model":      "claude-opus-4-5",
                    "max_tokens": 600,
                    "messages":   data.get("messages", [])
                }).encode("utf-8"),
                headers={
                    "Content-Type":      "application/json",
                    "x-api-key":         API_KEY,
                    "anthropic-version": "2023-06-01"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = resp.read()

            # Verbrauch erhoehen
            user["used"] = user.get("used", 0) + 1
            save_user(user)

            # Scan speichern
            save_scan({
                "email":    user["email"],
                "name":     user.get("name", ""),
                "datum":    datetime.now().strftime("%d.%m.%Y"),
                "filename": data.get("filename", ""),
                "ts":       datetime.now().isoformat(),
            })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(result)

        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            print(f"[CLAUDE FEHLER] {e.code}: {err[:300]}")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err.encode("utf-8"))

        except Exception as e:
            print(f"[SCAN FEHLER] {e}")
            self.send_json({"error": str(e)}, 500)

    # --- ADMIN ---
    def _check_admin(self):
        token = self.get_token()
        user  = get_session(token) if token else None
        if not user: return None, "Nicht eingeloggt"
        if user.get("role") not in ("admin", "superadmin"): return None, "Kein Admin"
        return user, None

    def _handle_admin_users(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        db    = db_load()
        users = list(db["users"].values())
        self.send_json({"ok": True, "users": users})

    def _handle_approve(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data   = self.read_body()
        email  = data.get("email", "").lower()
        quota  = int(data.get("quota", 500))
        price  = float(data.get("price", 9.99))
        target = get_user(email)
        if not target: self.send_json({"error": "Nutzer nicht gefunden"}, 404); return
        target["approved"] = True
        target["quota"]    = quota
        target["price"]    = price
        save_user(target)
        self.send_json({"ok": True})

    def _handle_update_user(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data   = self.read_body()
        email  = data.get("email", "").lower()
        target = get_user(email)
        if not target: self.send_json({"error": "Nutzer nicht gefunden"}, 404); return
        for k in ("name", "quota", "price", "active"):
            if k in data: target[k] = data[k]
        save_user(target)
        self.send_json({"ok": True})

    def _handle_delete_user(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        data   = self.read_body()
        email  = data.get("email", "").lower()
        db     = db_load()
        if email in db["users"]:
            del db["users"][email]
            db_save(db)
        self.send_json({"ok": True})

    def _handle_promote(self):
        # Nur Superadmin kann andere zu Admin machen
        token = self.get_token()
        user  = get_session(token) if token else None
        if not user or user.get("role") != "superadmin":
            self.send_json({"error": "Nur Superadmin"}, 403); return
        data   = self.read_body()
        email  = data.get("email", "").lower()
        role   = data.get("role", "nutzer")
        target = get_user(email)
        if not target: self.send_json({"error": "Nutzer nicht gefunden"}, 404); return
        target["role"] = role
        save_user(target)
        self.send_json({"ok": True})

    def _handle_stats(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        db     = db_load()
        users  = list(db["users"].values())
        active = sum(1 for u in users if u.get("active") and u.get("approved"))
        pend   = sum(1 for u in users if not u.get("approved"))
        rev    = sum(u.get("price", 0) for u in users if u.get("active") and u.get("approved"))
        scans_m = len([s for s in db["scans"] if s.get("datum","").endswith(datetime.now().strftime(".%m.%Y"))])
        self.send_json({
            "ok": True,
            "total_users":   len(users),
            "active_users":  active,
            "pending_users": pend,
            "monthly_scans": scans_m,
            "monthly_revenue": round(rev, 2),
        })

    def _handle_admin_scans(self):
        user, err = self._check_admin()
        if err: self.send_json({"error": err}, 403); return
        db = db_load()
        self.send_json({"ok": True, "scans": db["scans"][-100:]})


def main():
    ensure_superadmin()
    test_email()

    base = Path(__file__).parent
    print(f"\n{'='*50}")
    print(f"  ReceiptScanner Server")
    print(f"  Ordner: {base}")
    print(f"{'='*50}")

    # Ordner und Dateien pruefen
    needed = [
        base / "app" / "login.html",
        base / "app" / "index.html",
        base / "admin" / "index.html",
    ]
    alle_ok = True
    for f in needed:
        if f.exists():
            print(f"  [OK] {f.relative_to(base)}")
        else:
            print(f"  [FEHLT] {f.relative_to(base)}")
            alle_ok = False

    if not alle_ok:
        print("\n  FEHLER: Fehlende Dateien! Struktur pruefen:")
        print("  ReceiptScanner-System/")
        print("      server.py")
        print("      app/")
        print("          login.html")
        print("          index.html")
        print("      admin/")
        print("          index.html")
        input("\nEnter druecken zum Beenden...")
        return

    print(f"\n  Nutzer:  http://localhost:{PORT}/login")
    print(f"  Admin:   http://localhost:{PORT}/admin")
    print(f"  Stoppen: STRG+C")
    print(f"{'='*50}\n")

    import threading, webbrowser
    def open_b():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}/login")
    threading.Thread(target=open_b, daemon=True).start()

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server gestoppt")

if __name__ == "__main__":
    main()
