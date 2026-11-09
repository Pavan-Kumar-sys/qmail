import smtplib
import imaplib
import ssl
import email
from email.header import decode_header
from email.mime.text import MIMEText
import json
import textwrap

SMTP_SERVER = "smtp.gmail.com"
IMAP_SERVER = "imap.gmail.com"

def _create_ssl_context():
    """Creates an SSL context that won't get blocked by local antivirus or Python 3.7 certs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def send_real_quantum_email(sender_email: str, app_password: str, recipient_email: str, subject: str, locked_package: dict):
    """Sends a real quantum-encrypted email over Gmail SMTP with 76-char line wrapping."""
    clean_password = app_password.replace(" ", "").strip()
    
    # Pack JSON and wrap into 76-character lines so Gmail SMTP never closes the connection!
    raw_json = json.dumps(locked_package)
    wrapped_json = "\n".join(textwrap.wrap(raw_json, width=76))
    
    email_body = (
        "--- BEGIN QUANTUM ENCRYPTED MESSAGE ---\n"
        f"{wrapped_json}\n"
        "--- END QUANTUM ENCRYPTED MESSAGE ---"
    )
    
    msg = MIMEText(email_body, "plain", "utf-8")
    msg["Subject"] = f"[Q-MAIL] {subject}"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    
    context = _create_ssl_context()
    
    # Try Port 587 (STARTTLS) first, and fall back to Port 465 (SSL) if needed
    try:
        with smtplib.SMTP(SMTP_SERVER, 587, timeout=25) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, clean_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
    except Exception:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465, context=context, timeout=25) as server:
            server.ehlo()
            server.login(sender_email, clean_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())

def fetch_real_quantum_emails(user_email: str, app_password: str):
    """Fetches real [Q-MAIL] emails from Gmail IMAP and rejoins the wrapped quantum capsule."""
    clean_password = app_password.replace(" ", "").strip()
    results = []
    context = _create_ssl_context()
    
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993, ssl_context=context)
    try:
        mail.login(user_email, clean_password)
        mail.select("inbox")
        
        status, messages = mail.search(None, '(SUBJECT "[Q-MAIL]")')
        if status != "OK" or not messages[0]:
            return results
            
        email_ids = messages[0].split()[-10:]
        for e_id in reversed(email_ids):
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    raw_subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(raw_subject, bytes):
                        raw_subject = raw_subject.decode(encoding or "utf-8", errors="ignore")
                    clean_subject = raw_subject.replace("[Q-MAIL] ", "")
                    
                    sender = msg.get("From", "Unknown")
                    date_str = msg.get("Date", "")
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                        
                    if "--- BEGIN QUANTUM ENCRYPTED MESSAGE ---" in body:
                        try:
                            chunk = body.split("--- BEGIN QUANTUM ENCRYPTED MESSAGE ---")[1]
                            chunk = chunk.split("--- END QUANTUM ENCRYPTED MESSAGE ---")[0]
                            # Remove line breaks to reconstruct the JSON string
                            clean_json = "".join(chunk.split())
                            locked_data = json.loads(clean_json)
                            results.append({
                                "sender": sender,
                                "subject": clean_subject,
                                "timestamp": date_str,
                                "kem_capsule": locked_data["kem_capsule"],
                                "nonce": locked_data["nonce"],
                                "ciphertext": locked_data["ciphertext"]
                            })
                        except Exception:
                            pass
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return results