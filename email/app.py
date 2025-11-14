import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import os
import base64
from flask import Flask, redirect, url_for, session, render_template, send_file
from flask import request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
SCOPES = [os.getenv("GOOGLE_SCOPES")]

# ---------------------- HOME ----------------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------------- LOGIN ----------------------
@app.route("/auth/google")
def auth_google():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True)
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    session["state"] = state

    return redirect(auth_url)

# ---------------------- OAuth Callback ----------------------
@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("oauth2callback", _external=True)
    )

    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    return redirect(url_for("dashboard"))

# ---------------------- Dashboard ----------------------
@app.route("/dashboard")
def dashboard():
    if "credentials" not in session:
        return redirect(url_for("index"))

    creds = Credentials(**session["credentials"])
    gmail = build("gmail", "v1", credentials=creds)

    query = 'subject:(invoice OR statement OR "bank statement" OR receipt) has:attachment filename:pdf'

    results = gmail.users().messages().list(userId="me", q=query, maxResults=25).execute()
    messages = results.get("messages", [])

    emails = []

    for msg in messages:
        full_msg = gmail.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        snippet = full_msg.get("snippet", "")

        attachments = []
        parts = full_msg["payload"].get("parts", [])
        for part in parts:
            if part.get("filename") and part.get("body", {}).get("attachmentId"):
                attachments.append({
                    "filename": part["filename"],
                    "attachmentId": part["body"]["attachmentId"],
                    "messageId": msg["id"]
                })

        emails.append({
            "snippet": snippet,
            "attachments": attachments
        })

    return render_template("dashboard.html", emails=emails)

# ---------------------- Download Attachment ----------------------
@app.route("/download/<message_id>/<attachment_id>/<filename>")
def download(message_id, attachment_id, filename):

    creds = Credentials(**session["credentials"])
    gmail = build("gmail", "v1", credentials=creds)

    attachment = gmail.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=attachment_id
    ).execute()

    data = attachment["data"]
    file_data = base64.urlsafe_b64decode(data)

    return send_file(
        BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )

# ---------------------- LOGOUT ----------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------------------- RUN APP ----------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)