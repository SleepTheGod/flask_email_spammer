# flask_email_spammer
A fully automated, multithreaded Flask application that sends emails every second using rotating user agents and proxy chains to simulate evasion tactics against rate limits, for lab testing purposes only.
```
flask_email_sender/
├── app.py
├── database.py
├── requirements.txt
├── deploy.sh
├── .env.example
└── templates/
    ├── index.html
    └── email_templates/
        ├── welcome.txt
        └── newsletter.txt
```
