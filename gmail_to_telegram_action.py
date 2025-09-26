# gmail_to_telegram_action.py
import os
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import requests
from datetime import datetime, timedelta, timezone

# Ayarlar: GitHub Secrets üzerinden alınıyor
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MAX_EMAILS = int(os.environ.get("MAX_EMAILS", "20"))

def decode_str(s):
    if not s:
        return ""
    parts = decode_header(s)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="ignore")
        else:
            result += part
    return result

def get_text_from_msg(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
    else:
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    return ""

def first_sentence(text, max_chars=200):
    if not text:
        return "(Boş içerik)"
    for sep in ["\r\n", "\n", ". ", "? ", "! "]:
        if sep in text:
            part = text.split(sep)[0].strip()
            if part:
                return (part[:max_chars] + "...") if len(part) > max_chars else part
    return (text[:max_chars] + "...") if len(text) > max_chars else text

def fetch_today_emails():
    rv = []
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        M.select("inbox")
        typ, data = M.search(None, "ALL")
        ids = data[0].split()
        ids = ids[-MAX_EMAILS:]
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=1)
        for num in ids[::-1]:
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != 'OK':
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            date_hdr = msg.get("Date")
            try:
                msg_date = parsedate_to_datetime(date_hdr)
            except:
                continue
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
            if msg_date < cutoff:
                continue
            subj = decode_str(msg.get("Subject", "(No Subject)"))
            body = get_text_from_msg(msg)
            rv.append({"subject": subj, "body": body})
        M.logout()
    except Exception as e:
        print("Hata (IMAP):", e)
    return rv

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(text) > 3900:
        text = text[:3900] + "\n\n...(truncated)"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=15)
        print("Telegram status:", r.status_code)
    except Exception as e:
        print("Telegram gönderme hatası:", e)

def main():
    emails = fetch_today_emails()
    today_str = datetime.now().strftime("%d %b %Y")
    if not emails:
        report = f"📭 {today_str} — Bugün yeni mail yok."
    else:
        report = f"📌 Günlük Mail Özeti ({today_str})\n\n"
        for e in emails:
            s = first_sentence(e["body"])
            report += f"📩 {e['subject']}\n📝 {s}\n\n"
    print(report)
    send_telegram(report)

if __name__ == "__main__":
    main()
