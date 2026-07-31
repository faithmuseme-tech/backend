import urllib.parse
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/gmail.send'
REDIRECT_URI = 'http://localhost:8000/gmail/callback/'


class Command(BaseCommand):
    help = 'One-time Gmail OAuth2 authorization — prints the refresh token to add to .env'

    def handle(self, *args, **kwargs):
        params = {
            'client_id': settings.GMAIL_CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': SCOPE,
            'access_type': 'offline',
            'prompt': 'consent',
        }
        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
        self.stdout.write(f'\n1. Open this URL in your browser:\n\n   {url}\n')
        self.stdout.write('\n2. After authorizing, paste the "code" from the redirect URL:\n')
        code = input('   code: ').strip()

        resp = requests.post(TOKEN_URL, data={
            'code': code,
            'client_id': settings.GMAIL_CLIENT_ID,
            'client_secret': settings.GMAIL_CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        refresh_token = data.get('refresh_token')
        if refresh_token:
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Add this to your .env:\n\n   GMAIL_REFRESH_TOKEN={refresh_token}\n'
            ))
        else:
            self.stdout.write(self.style.ERROR('\n❌ No refresh_token returned. Make sure prompt=consent was used.'))
