#!/usr/bin/env python3
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/meetings.space.readonly',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

CREDS_FILE = '/home/conti/.nanobot/workspace/google-workspace/credentials.json'
TOKEN_FILE = '/home/conti/.nanobot/workspace/google-workspace/token.json'

flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
flow.redirect_uri = 'http://localhost:8000/'

auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent')

print("="*60)
print("📋 COPIÁ ESTA URL Y ABRILA EN TU NAVEGADOR:")
print("="*60)
print()
print(auth_url)
print()
print("="*60)
print("Después de autorizar, pegá el código aquí abajo:")
print("="*60)

code = input("\nCódigo: ")

# Intercambiar código por token
flow.fetch_token(code=code)
creds = flow.credentials

# Guardar token
with open(TOKEN_FILE, 'w') as f:
    f.write(creds.to_json())

print("\n✅ Token guardado con TODOS los permisos de Google Workspace!")
