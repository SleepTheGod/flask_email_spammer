import os
import threading
import time
import smtplib
import random
import queue # New import for thread-safe queue
from email.mime.text import MIMEText
from flask import Flask, render_template, request
from dotenv import load_dotenv
import socks
import smtplib
import requests

load_dotenv()

app = Flask(__name__)

# --- Configuration from Environment Variables ---
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')

# --- Dynamic Proxy Fetching ---
PROXY_SCRAPE_URL = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=all"

def fetch_proxies(url):
    """Fetches a list of proxies from the given URL."""
    try:
        print(f"[INIT] Attempting to fetch proxies from: {url}")
        response = requests.get(url, timeout=20) # Increased timeout for external API
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        proxies = [p.strip() for p in response.text.splitlines() if p.strip()]
        print(f"[INIT] Successfully fetched {len(proxies)} proxies.")
        return proxies
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch proxies from {url}: {e}")
        return []

# Initialize PROXIES list at startup
PROXIES = fetch_proxies(PROXY_SCRAPE_URL)
if not PROXIES:
    print("[WARNING] No proxies fetched from ProxyScrape. Falling back to PROXIES environment variable.")
    PROXIES = [p.strip() for p in os.getenv('PROXIES', '').split(',') if p.strip()]
    if not PROXIES:
        print("[CRITICAL] No proxies available from any source. Email sending will likely fail.")

# USER_AGENTS are expected to be comma-separated strings from .env
USER_AGENTS = [ua.strip() for ua in os.getenv('USER_AGENTS', '').split(',') if ua.strip()]
if not USER_AGENTS:
    print("[WARNING] No USER_AGENTS configured. Using a default one.")
    USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"]

# --- Global Queue and Log ---
email_task_queue = queue.Queue()
SENT_LOG = []
LOG_MAX_SIZE = 100 # Keep log size manageable

# --- Email Sending Worker ---
def send_email_worker():
    """
    Worker thread function that continuously pulls email tasks from the queue
    and attempts to send them.
    """
    while True:
        try:
            recipient, subject, body = email_task_queue.get(timeout=5) # Wait for tasks
            selected_proxy = "N/A"
            try:
                if not PROXIES:
                    raise ValueError("No active proxies available. Cannot send email.")
                if not USER_AGENTS:
                    raise ValueError("No user agents configured. Cannot send email.")

                selected_proxy = random.choice(PROXIES)
                ua = random.choice(USER_AGENTS)
                ip, port_str = selected_proxy.split(':')
                port = int(port_str)

                # Configure SOCKS proxy for smtplib
                socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, ip, port)
                socks.wrapmodule(smtplib)

                msg = MIMEText(body)
                msg['From'] = SMTP_USER
                msg['To'] = recipient
                msg['Subject'] = subject
                msg['User-Agent'] = ua # Custom header for user agent

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server: # Added timeout for SMTP connection
                    server.starttls() # Secure the connection
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_USER, recipient, msg.as_string())
                
                log_entry = f"[SUCCESS] Payload delivered to {recipient} via {selected_proxy} at {time.strftime('%H:%M:%S')}"
                print(log_entry)
                SENT_LOG.append(log_entry)
            except Exception as e:
                log_entry = f"[ERROR] Failed to inject to {recipient} via {selected_proxy}: {e} at {time.strftime('%H:%M:%S')}"
                print(log_entry)
                SENT_LOG.append(log_entry)
            finally:
                email_task_queue.task_done() # Mark task as done
                # Trim log to max size
                if len(SENT_LOG) > LOG_MAX_SIZE:
                    SENT_LOG.pop(0) # Remove oldest entry
        except queue.Empty:
            # No tasks in queue, continue waiting
            pass
        except Exception as e:
            print(f"[CRITICAL WORKER ERROR] {e}")

# --- Spam Campaign Producer ---
def start_spam_campaign(subject, body, recipients):
    """
    Starts a background thread to continuously add email tasks to the queue.
    """
    def producer_loop():
        while True:
            if not recipients:
                log_entry = f"[INFO] No targets in queue. Awaiting input... at {time.strftime('%H:%M:%S')}"
                if not SENT_LOG or SENT_LOG[-1] != log_entry: # Avoid spamming log with same message
                    print(log_entry)
                    SENT_LOG.append(log_entry)
                    if len(SENT_LOG) > LOG_MAX_SIZE: SENT_LOG.pop(0)
                time.sleep(5) # Wait if no recipients
                continue

            for recipient in recipients:
                email_task_queue.put((recipient, subject, body))
                # Minimal delay to allow other threads/processes to run, but still very fast
                time.sleep(0.001) # Adjust for desired speed and system load

    # Start the producer loop in a daemon thread
    if not hasattr(app, 'producer_thread') or not app.producer_thread.is_alive():
        app.producer_thread = threading.Thread(target=producer_loop, daemon=True)
        app.producer_thread.start()
        print(f"[INFO] CyberMail Injection producer loop initiated. at {time.strftime('%H:%M:%S')}")
    else:
        print(f"[INFO] Producer loop already active. Adding new targets/payloads. at {time.strftime('%H:%M:%S')}")


# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Handles the main page, displaying the form and recent logs.
    Processes form submissions to add recipients and start campaigns.
    """
    if request.method == 'POST':
        subject = request.form['subject']
        message_type = request.form['message']
        raw_recipients = request.form['recipient']

        # Parse multiple recipients from textarea
        recipients = [
            email.strip() 
            for email in raw_recipients.replace(',', '\n').splitlines() 
            if email.strip()
        ]

        if not recipients:
            log_entry = f"[WARNING] No target emails provided. Injection aborted. at {time.strftime('%H:%M:%S')}"
            print(log_entry)
            SENT_LOG.append(log_entry)
            if len(SENT_LOG) > LOG_MAX_SIZE: SENT_LOG.pop(0)
            return render_template('index.html', log=SENT_LOG[-LOG_MAX_SIZE:])

        # Start the campaign (or ensure it's running) with the new parameters and recipients
        start_spam_campaign(subject, body_from_template(message_type), recipients)
        
        log_entry = f"[INFO] Injection parameters updated. Targets: {len(recipients)}. Payload: '{message_type}'. at {time.strftime('%H:%M:%S')}"
        print(log_entry)
        SENT_LOG.append(log_entry)
        if len(SENT_LOG) > LOG_MAX_SIZE: SENT_LOG.pop(0)
        return render_template('index.html', log=SENT_LOG[-LOG_MAX_SIZE:])
    
    # For GET requests, just render the page with the last N log entries
    return render_template('index.html', log=SENT_LOG[-LOG_MAX_SIZE:])

# --- Template Loading Helper ---
def body_from_template(message_type):
    template_path = f'templates/email_templates/{message_type}.txt'
    if not os.path.exists(template_path):
        log_entry = f"[ERROR] Payload type '{message_type}' template not found. at {time.strftime('%H:%M:%S')}"
        print(log_entry)
        SENT_LOG.append(log_entry)
        if len(SENT_LOG) > LOG_MAX_SIZE: SENT_LOG.pop(0)
        return "Error: Template not found."
    with open(template_path, 'r') as f:
        return f.read()

# --- Application Entry Point ---
if __name__ == '__main__':
    # Ensure the templates directory exists
    os.makedirs('templates/email_templates', exist_ok=True)
    
    # Create default templates if they don't exist
    default_templates = {
        'welcome': "Welcome to our secure network. Your access credentials will be provided shortly.",
        'newsletter': "Stay updated with the latest cyber intelligence. Subscribe to our newsletter.",
        'alert': "URGENT: Unauthorized access detected. Review system logs immediately."
    }
    for name, content in default_templates.items():
        path = f'templates/email_templates/{name}.txt'
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(content)

    # Start worker threads for sending emails
    NUM_WORKER_THREADS = 20 # Adjust based on system resources and desired speed
    for _ in range(NUM_WORKER_THREADS):
        worker = threading.Thread(target=send_email_worker, daemon=True)
        worker.start()
    print(f"[INIT] Started {NUM_WORKER_THREADS} email sending worker threads.")

    # Start the Flask development server
    app.run(debug=True)
