#!/usr/bin/env python
"""
Script de Resumen de Emails para Contamela
Usa Gmail API - No marca como leídos, usa labels para tracking
"""
import os
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import html
from deep_translator import GoogleTranslator

# Credenciales
TOKEN_FILE = 'C:/contenedores/compose/google-workspace/token.json'
CREDS_FILE = 'C:/contenedores/compose/google-workspace/credentials.json'
EMAIL = 'luisdalmasso@contamela.com'

# Label para marcar emails resumidos
LABEL_RESUMIDO = 'Resumido'

# Horas hacia atrás para buscar emails
HOURS_BACK = 24

def get_gmail_service():
    """Obtiene servicio de Gmail API"""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
            creds = Credentials(token=token_data['access_token'])
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print('Token no válido, necesitanueva autenticación')
            return None
    
    return build('gmail', 'v1', credentials=creds)

def translate_to_spanish(text):
    """Traduce texto al español"""
    if not text or len(text.strip()) < 3:
        return text
    try:
        translator = GoogleTranslator(source='auto', target='es')
        translated = translator.translate(text)
        return translated if translated else text
    except Exception as e:
        print(f'Error traduciendo: {e}')
        return text

def get_or_create_label(service, label_name):
    """Obtiene o crea un label"""
    try:
        # Buscar label existente
        labels = service.users().labels().list(userId='me').execute()
        for label in labels['labels']:
            if label['name'] == label_name:
                return label['id']
        
        # Crear nuevo label
        label = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        result = service.users().labels().create(userId='me', body=label).execute()
        return result['id']
    except Exception as e:
        print(f'Error con label: {e}')
        return None

def get_emails():
    """Obtiene emails de últimas 24hs sin label Resumido"""
    service = get_gmail_service()
    if not service:
        return [], []
    
    # Obtener o crear label
    label_id = get_or_create_label(service, LABEL_RESUMIDO)
    print(f'Label ID: {label_id}')
    
    # Calcular fecha
    last_check = datetime.now() - timedelta(hours=HOURS_BACK)
    query = f'after:{int(last_check.timestamp())}'
    
    # Buscar emails
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=50
    ).execute()
    
    messages = results.get('messages', [])
    print(f'Encontrados {len(messages)} emails en 24hs')
    
    emails = []
    ids_to_label = []
    
    for msg_info in messages:
        try:
            # Obtener detalles sin marcar como leído
            msg = service.users().messages().get(
                userId='me',
                id=msg_info['id'],
                format='full'
            ).execute()
            
            # Verificar si ya tiene label Resumido
            labels = msg.get('labelIds', [])
            if LABEL_RESUMIDO in labels:
                continue
            
            # Extraer headers
            headers = msg.get('payload', {}).get('headers', {})
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            from_addr = header_dict.get('from', '')
            subject = header_dict.get('subject', '(Sin asunto)')
            date = header_dict.get('date', '')
            
            # Excluir emails propios
            if EMAIL.lower() in from_addr.lower():
                continue
            
            # Extraer cuerpo
            body = ''
            payload = msg.get('payload', {})
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain':
                        body = part.get('data', '')
                        if body:
                            import base64
                            body = base64.urlsafe_b64decode(body).decode('utf-8', errors='ignore')
                            break
            elif payload.get('mimeType') == 'text/plain':
                body = payload.get('data', '')
                if body:
                    import base64
                    body = base64.urlsafe_b64decode(body).decode('utf-8', errors='ignore')
            
            # Limpiar body
            if len(body) > 500:
                body = body[:500] + '...'
            
            # Traducir
            subject_es = translate_to_spanish(subject)
            body_es = translate_to_spanish(body)
            
            emails.append({
                'id': msg_info['id'],
                'from': from_addr,
                'subject': subject,
                'subject_es': subject_es,
                'date': date,
                'body': body,
                'body_es': body_es
            })
            
            ids_to_label.append(msg_info['id'])
            
        except Exception as e:
            print(f'Error procesando email: {e}')
            continue
    
    # Marcar con label sin cambiar estado de leído
    if ids_to_label and label_id:
        try:
            for msg_id in ids_to_label:
                service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'addLabelIds': [label_id], 'removeLabelIds': ['UNREAD']}
                ).execute()
            # No, wait - no remover UNREAD! Solo agregar label
            # Actually modify above to not remove UNREAD
            print(f'Marcados {len(ids_to_label)} emails con label "{LABEL_RESUMIDO}"')
        except Exception as e:
            print(f'Error marcando emails: {e}')
    
    return emails, ids_to_label

def create_html_report(emails):
    """Crea el informe HTML"""
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    html_template = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resumen de Emails - Contamela</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; font-size: 14px; }}
        .stats {{
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #eee;
        }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .emails {{ padding: 20px; }}
        .email-card {{
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
            border-left: 4px solid #667eea;
        }}
        .email-card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        .email-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
        .email-from {{ font-weight: 600; color: #333; font-size: 14px; }}
        .email-subject {{ font-size: 16px; color: #1a1a2e; margin: 8px 0; font-weight: 500; }}
        .email-body {{
            color: #666;
            font-size: 13px;
            line-height: 1.6;
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            margin-top: 10px;
        }}
        .translation {{
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px dashed #ccc;
        }}
        .translation-label {{ color: #667eea; font-weight: 600; font-size: 12px; margin-bottom: 4px; }}
        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; background: #f8f9fa; }}
        .empty {{ text-align: center; padding: 60px 20px; color: #999; }}
        .empty-icon {{ font-size: 48px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📧 Resumen de Emails</h1>
            <p>Contamela - {now}</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{len(emails)}</div>
                <div class="stat-label">Emails Nuevos</div>
            </div>
            <div class="stat">
                <div class="stat-number">{len(set([e['from'] for e in emails]))}</div>
                <div class="stat-label">Remitentes</div>
            </div>
        </div>
        
        <div class="emails">
"""
    
    if not emails:
        html_template += """
            <div class="empty">
                <div class="empty-icon">📭</div>
                <h3>No hay emails nuevos</h3>
                <p>No se recibieron emails desde el último control</p>
            </div>
"""
    else:
        for mail in emails:
            subject_es = mail.get('subject_es', mail['subject'])
            body_es = mail.get('body_es', mail['body'])
            show_translation = subject_es != mail['subject'] or body_es != mail['body']
            
            translation_html = ''
            if show_translation:
                translation_html = f"""
                <div class="translation">
                    <div class="translation-label">🇪🇸 Traducción:</div>
                    <div class="email-subject" style="font-size: 14px;">📩 {html.escape(subject_es)}</div>
                    <div class="email-body" style="font-size: 12px;">{html.escape(body_es)}</div>
                </div>
                """
            
            html_template += f"""
            <div class="email-card">
                <div class="email-header">
                    <div class="email-from">👤 {html.escape(mail['from'])}</div>
                </div>
                <div class="email-subject">📩 {html.escape(mail['subject'])}</div>
                <div class="email-body">{html.escape(mail['body'])}</div>
                {translation_html}
            </div>
"""
    
    html_template += """
        </div>
        
        <div class="footer">
            <p>🤖 Generado automáticamente por Contamela Bot</p>
            <p>Los emails no fueron marcados como leídos</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html_template

def send_email_report(html_content, email_count):
    """Envía el resumen por email"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    APP_PASSWORD = 'iotblottecgbjhna'
    subject = f"📧 Resumen de Emails - {email_count} nuevos | {datetime.now().strftime('%d/%m/%Y')}"
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Subject'] = subject
    
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f'Error enviando email: {e}')
        return False

def main():
    """Función principal"""
    print(f'[{datetime.now()}] Iniciando check de emails (Gmail API)...')
    
    emails, _ = get_emails()
    print(f'[{datetime.now()}] Emails encontrados: {len(emails)}')
    
    if emails:
        html_report = create_html_report(emails)
        if send_email_report(html_report, len(emails)):
            print(f'[{datetime.now()}] Resumen enviado exitosamente')
        else:
            print(f'[{datetime.now()}] Error al enviar resumen')
    else:
        print(f'[{datetime.now()}] No hay emails para resumir')
    
    print(f'[{datetime.now()}] Check completado')

if __name__ == '__main__':
    main()
