import base64
import requests
from email.mime.text import MIMEText
from django.conf import settings


def _get_access_token():
    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.GMAIL_CLIENT_ID,
        'client_secret': settings.GMAIL_CLIENT_SECRET,
        'refresh_token': settings.GMAIL_REFRESH_TOKEN,
        'grant_type': 'refresh_token',
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()['access_token']


def send_email(to: str, subject: str, html: str):
    msg = MIMEText(html, 'html')
    msg['to'] = to
    msg['subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    access_token = _get_access_token()
    resp = requests.post(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        headers={'Authorization': f'Bearer {access_token}'},
        json={'raw': raw},
        timeout=10,
    )
    resp.raise_for_status()
