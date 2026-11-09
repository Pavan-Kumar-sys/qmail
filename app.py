import warnings
warnings.filterwarnings("ignore")

import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from quantum_crypto import generate_quantum_keys, encrypt_email, decrypt_email
from database import init_db, DB_NAME
from real_mail import send_real_quantum_email, fetch_real_quantum_emails

app = Flask(__name__)
init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    current_user = request.args.get("user", "alice@qmail.com")
    status_msg = request.args.get("msg", "")
    conn = get_db()
    
    users = conn.execute("SELECT email, name, public_key FROM users").fetchall()
    user_info = conn.execute("SELECT * FROM users WHERE email = ?", (current_user,)).fetchone()
    
    raw_emails = conn.execute(
        "SELECT * FROM emails WHERE recipient = ? ORDER BY id DESC", (current_user,)
    ).fetchall()
    
    inbox = []
    for mail in raw_emails:
        try:
            decrypted_body = decrypt_email(
                user_info["secret_key"],
                mail["kem_capsule"],
                mail["nonce"],
                mail["ciphertext"]
            )
        except Exception:
            decrypted_body = "[Decryption Failed - Invalid Quantum Key]"
            
        inbox.append({
            "id": mail["id"],
            "sender": mail["sender"],
            "subject": mail["subject"],
            "decrypted_body": decrypted_body,
            "ciphertext": mail["ciphertext"],
            "kem_capsule": mail["kem_capsule"],
            "nonce": mail["nonce"],
            "timestamp": mail["timestamp"]
        })
        
    conn.close()
    return render_template("index.html", users=users, current_user=user_info, inbox=inbox, status_msg=status_msg)

@app.route("/send", methods=["POST"])
def send_email():
    sender = request.form["sender"]
    recipient = request.form["recipient"]
    subject = request.form["subject"]
    body = request.form["body"]
    app_password = request.form.get("app_password", "").strip()
    
    conn = get_db()
    recipient_info = conn.execute("SELECT public_key FROM users WHERE email = ?", (recipient,)).fetchone()
    
    msg = "Email locked and saved to local inbox!"
    if recipient_info:
        locked = encrypt_email(recipient_info["public_key"], body)
        
        # If user entered their 16-letter Google App Password, send a REAL email over Gmail!
        if app_password:
            try:
                send_real_quantum_email(sender, app_password, recipient, subject, locked)
                msg = f"Real Quantum Email sent over Gmail SMTP to {recipient}!"
            except Exception as e:
                conn.close()
                return redirect(url_for("index", user=sender, msg=f"Gmail Error: {str(e)}"))
                
        conn.execute(
            "INSERT INTO emails (sender, recipient, subject, kem_capsule, nonce, ciphertext) VALUES (?, ?, ?, ?, ?, ?)",
            (sender, recipient, subject, locked["kem_capsule"], locked["nonce"], locked["ciphertext"])
        )
        conn.commit()
        
    conn.close()
    return redirect(url_for("index", user=sender, msg=msg))

@app.route("/sync_gmail", methods=["POST"])
def sync_gmail():
    user_email = request.form["user_email"]
    app_password = request.form["app_password"].strip()
    
    try:
        fetched = fetch_real_quantum_emails(user_email, app_password)
        conn = get_db()
        count = 0
        for item in fetched:
            exists = conn.execute(
                "SELECT id FROM emails WHERE recipient = ? AND ciphertext = ?",
                (user_email, item["ciphertext"])
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO emails (sender, recipient, subject, kem_capsule, nonce, ciphertext, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item["sender"], user_email, item["subject"], item["kem_capsule"], item["nonce"], item["ciphertext"], item["timestamp"])
                )
                count += 1
        conn.commit()
        conn.close()
        return redirect(url_for("index", user=user_email, msg=f"Synced {count} new Quantum Email(s) from real Gmail IMAP!"))
    except Exception as e:
        return redirect(url_for("index", user=user_email, msg=f"Gmail Sync Error: {str(e)}"))

@app.route("/new_user", methods=["POST"])
def new_user():
    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    if name and email:
        conn = get_db()
        exists = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
        if not exists:
            keys = generate_quantum_keys()
            conn.execute(
                "INSERT INTO users (email, name, public_key, secret_key) VALUES (?, ?, ?, ?)",
                (email, name, keys["public_key"], keys["secret_key"])
            )
            conn.commit()
        conn.close()
        return redirect(url_for("index", user=email, msg=f"Generated Quantum Lattice Keypair for {email}!"))
    return redirect(url_for("index"))

if __name__ == "__main__":
    print("Quantum Email Server is starting! Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)