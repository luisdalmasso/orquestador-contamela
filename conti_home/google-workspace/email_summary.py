import os, json, sys
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import html
from deep_translator import GoogleTranslator

TOKEN_FILE = '/home/conti/.nanobot/workspace/google-workspace/token.json'
EMAIL = 'luisdalmasso@contamela.com'
LABEL_RESUMIDO = 'Label_2'
HOURS_BACK = 168
APP_PASSWORD = 'iotblottecgbjhna'

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    
    return build('gmail', 'v1', credentials=creds) if creds else None

def translate_to_spanish(text):
    if not text or len(text.strip()) < 3:
        return text
    try:
        translator = GoogleTranslator(source='auto', target='es')
        return translator.translate(text) or text
    except:
        return text

def escape_html(text):
    return html.escape(text) if text else ''

def get_emails():
    service = get_gmail_service()
    if not service:
        return []
    
    last_check = datetime.now() - timedelta(hours=HOURS_BACK)
    query = f'after:{int(last_check.timestamp())}'
    
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])
    
    emails = []
    for msg_info in messages:
        msg = service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
        labels = msg.get('labelIds', [])
        if LABEL_RESUMIDO in labels:
            continue
        
        headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', {})}
        from_addr = headers.get('from', '')
        if EMAIL.lower() in from_addr.lower():
            continue
        
        subject = headers.get('subject', '(Sin asunto)')
        body = ''
        
        payload = msg.get('payload', {})
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    body = part.get('data', '')
                    if body:
                        import base64
                        body = base64.urlsafe_b64decode(body).decode('utf-8', errors='ignore')[:500]
                        break
        
        emails.append({
            'id': msg_info['id'],
            'from': from_addr,
            'subject': subject,
            'body': body,
            'subject_es': translate_to_spanish(subject),
            'body_es': translate_to_spanish(body) if body else ''
        })
    
    return emails

def create_html_report(emails):
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    rows = ''
    for mail in emails:
        trans = ''
        if mail['subject_es'] != mail['subject'] or mail['body_es'] != mail['body']:
            trans = f"<div class='translation'><div class='translation-label'> Traduccion:</div><div class='email-subject' style='font-size:14px'> {escape_html(mail['subject_es'])}</div><div class='email-body' style='font-size:12px'>{escape_html(mail['body_es'])}</div></div>"
        rows += f"<div class='email-card'><div class='email-from'> {escape_html(mail['from'])}</div><div class='email-subject'> {escape_html(mail['subject'])}</div><div class='email-body'>{escape_html(mail['body'])}</div>{trans}</div>"
    
    html_content = f"""<!DOCTYPE html><html><head><style>
    body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg,#1a1a2e,#16213e); min-height:100vh; padding:20px; }}
    .container {{ max-width:800px; margin:0 auto; background:#fff; border-radius:20px; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,0.3); }}
    .header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:white; padding:30px; text-align:center; }}
    .header h1 {{ font-size:28px; margin-bottom:10px; }}
    .stats {{ display:flex; justify-content:space-around; padding:20px; background:#f8f9fa; border-bottom:1px solid #eee; }}
    .stat-number {{ font-size:32px; font-weight:bold; color:#667eea; }}
    .stat-label {{ font-size:12px; color:#666; text-transform:uppercase; }}
    .emails {{ padding:20px; }}
    .email-card {{ background:#fff; border:1px solid #e0e0e0; border-radius:12px; padding:20px; margin-bottom:15px; border-left:4px solid #667eea; }}
    .email-from {{ font-weight:600; color:#333; font-size:14px; }}
    .email-subject {{ font-size:16px; color:#1a1a2e; margin:8px 0; font-weight:500; }}
    .email-body {{ color:#666; font-size:13px; line-height:1.6; background:#f8f9fa; padding:12px; border-radius:8px; margin-top:10px; }}
    .translation {{ margin-top:8px; padding-top:8px; border-top:1px dashed #ccc; }}
    .translation-label {{ color:#667eea; font-weight:600; font-size:12px; }}
    .footer {{ text-align:center; padding:20px; color:#999; font-size:12px; background:#f8f9fa; }}
    </style></head><body>
    <div class='container'>
    <div class='header'><h1> Resumen de Emails</h1><p>Contamela - {now}</p></div>
    <div class='stats'><div class='stat'><div class='stat-number'>{len(emails)}</div><div class='stat-label'>Emails Nuevos</div></div>
    <div class='stat'><div class='stat-number'>{len(set([e['from'] for e in emails]))}</div><div class='stat-label'>Remitentes</div></div></div>
    <div class='emails'>{rows}</div>
    <div class='footer'><p>Los emails no fueron marcados como leidos</p></div>
    </div></body></html>"""
    return html_content

def mark_as_resumido(service, msg_ids):
    """Marca los emails con el label Resumido"""
    if not msg_ids:
        return
    
    # Obtener label ID
    labels = service.users().labels().list(userId='me').execute()
    label_id = None
    for l in labels['labels']:
        if l['name'] == 'Resumido':
            label_id = l['id']
            break
    
    if not label_id:
        print('WARNING: No se encontró el label Resumido')
        return
    
    # Marcar cada email
    for msg_id in msg_ids:
        try:
            service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            print(f'  Marcado: {msg_id[:15]}...')
        except Exception as e:
            print(f'  Error marcando {msg_id[:15]}: {e}')

def send_email(html_content, count):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    subject = f" Resumen de Emails - {count} nuevos | {datetime.now().strftime('%d/%m/%Y')}"
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL, APP_PASSWORD)
    server.send_message(msg)
    server.quit()

print('Iniciando...')
service = get_gmail_service()
emails = get_emails()
print(f'Emails: {len(emails)}')

if emails:
    # Guardar IDs para marcar después
    msg_ids = [e['id'] for e in emails]
    
    html = create_html_report(emails)
    send_email(html, len(emails))
    
    # Marcar emails como Resumido
    mark_as_resumido(service, msg_ids)
    
    print('Enviado!')
else:
    print('Sin emails')
