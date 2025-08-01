import os
import threading
import time
import smtplib
import random
from email.mime.text import MIMEText
from flask import Flask, render_template, request
from dotenv import load_dotenv
import socks
import smtplib

load_dotenv()

app = Flask(__name__)

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
PROXIES = os.getenv('PROXIES', '').split(',')
USER_AGENTS = os.getenv('USER_AGENTS', '').split(',')

RECIPIENT_LIST = []  # in-memory for testing; consider DB for production
SENT_LOG = []

def send_email(recipient, subject, body):
    try:
        proxy = random.choice(PROXIES)
        ua = random.choice(USER_AGENTS)

        ip, port = proxy.split(':')
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, ip, int(port))
        socks.wrapmodule(smtplib)

        msg = MIMEText(body)
        msg['From'] = SMTP_USER
        msg['To'] = recipient
        msg['Subject'] = subject
        msg['User-Agent'] = ua

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient, msg.as_string())

        SENT_LOG.append(f"Sent to {recipient} via {proxy}")
    except Exception as e:
        SENT_LOG.append(f"Failed to send to {recipient}: {e}")

def start_spam_campaign(subject, body):
    def loop_send():
        while True:
            for recipient in RECIPIENT_LIST:
                threading.Thread(target=send_email, args=(recipient, subject, body)).start()
                time.sleep(1)  # throttle for testing

    threading.Thread(target=loop_send).start()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        subject = request.form['subject']
        message_type = request.form['message']
        recipient = request.form['recipient']
        RECIPIENT_LIST.append(recipient)

        template_path = f'templates/email_templates/{message_type}.txt'
        if not os.path.exists(template_path):
            return "Template not found.", 400

        with open(template_path, 'r') as f:
            body = f.read()

        start_spam_campaign(subject, body)
        return "Spamming started in background."

    return render_template('index.html', log=SENT_LOG[-20:])

if __name__ == '__main__':
    app.run(debug=True)
