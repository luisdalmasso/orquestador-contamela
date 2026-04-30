#!/usr/bin/env python3
"""
Email Summary - Resumen de correos de las últimas 6 horas
Envía resumen en español usando Gmail SMTP
"""
import os
import sys
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Credenciales
GMAIL_USER = 'luisdalmasso@contamela.com'
GMAIL_APP_PASSWORD = 'iotb lott ecgb jhna'  # App Password

def get_emails_from_gmail():
    """Obtiene correos de las últimas 6 horas usando Gmail API"""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Cargar token
        token_path = '/home/conti/.nanobot/workspace/credentials/gmail_token.json'
        if not os.path.exists(token_path):
            print("Token no encontrado, intentando IMAP...")
            return get_emails_imap()
        
        creds = Credentials.from_authorized_user_info(
            json.loads(open(token_path).read()),
            ['https://www.googleapis.com/auth/gmail.readonly']
        )
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Rango de tiempo: últimas 6 horas
        now = datetime.now()
        start_time = now - timedelta(hours=6)
        
        # Buscar correos en INBOX después de start_time
        query = f'after:{int(start_time.timestamp())}'
        
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date', 'Snippet']
            ).execute()
            
            headers = msg_data.get('payload', {}).get('headers', [])
            email_info = {
                'id': msg['id'],
                'from': next((h['value'] for h in headers if h['name'] == 'From'), ''),
                'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), ''),
                'date': next((h['value'] for h in headers if h['name'] == 'Date'), ''),
                'snippet': msg_data.get('snippet', '')
            }
            emails.append(email_info)
        
        return emails
        
    except Exception as e:
        print(f"Error con Gmail API: {e}")
        return get_emails_imap()

def get_emails_imap():
    """Fallback: obtener correos usando IMAP"""
    import imaplib
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select('INBOX')
        
        # Buscar correos de últimas 6 horas (formato: dd-bbb-YYYY)
        now = datetime.now()
        start_time = now - timedelta(hours=6)
        date_str = start_time.strftime('%d-%b-%Y')
        
        print(f"Buscando correos desde: {date_str}")
        
        typ, messages = mail.search(None, f'SINCE {date_str}')
        msg_ids = messages[0].split()
        
        print(f"IMAP: {len(msg_ids)} mensajes encontrados")
        
        import email
        email_list = []
        for num in msg_ids[-20:]:  # Últimos 20
            typ, msg_data = mail.fetch(num, '(RFC822)')
            if msg_data and msg_data[0]:
                msg = email.message_from_bytes(msg_data[0][1])
                email_list.append({
                    'from': email.utils.parseaddr(msg.get('From', ''))[1] or msg.get('From', ''),
                    'subject': msg.get('Subject', 'Sin asunto'),
                    'date': msg.get('Date', ''),
                    'snippet': ''
                })
        
        mail.close()
        mail.logout()
        return email_list
        
    except Exception as e:
        print(f"Error IMAP: {e}")
        return []

def translate_subject(subject):
    """Traduce subjects de inglés a español si es necesario"""
    translations = {
        'Daily Summary': 'Resumen Diario',
        'Weekly Report': 'Informe Semanal',
        'Alert': 'Alerta',
        'Notification': 'Notificación',
        'Error': 'Error',
        'Warning': 'Advertencia',
        'Info': 'Información',
    }
    
    for eng, esp in translations.items():
        if eng.lower() in subject.lower():
            return subject.replace(eng, esp).replace(eng.lower(), esp.lower())
    return subject

def generate_html_summary(emails):
    """Genera HTML con el resumen de emails"""
    
    if not emails:
        html = """
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">📧 Resumen de Emails - 12pm a 6pm</h2>
            <p style="color: #7f8c8d;">No se encontraron correos en las últimas 6 horas.</p>
        </div>
        """
        return html
    
    rows = ""
    for email in emails:
        from_email = email.get('from', 'Desconocido')
        subject = translate_subject(email.get('subject', 'Sin asunto'))
        snippet = email.get('snippet', '')[:100]
        
        rows += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 12px; color: #3498db;">{from_email}</td>
            <td style="padding: 12px; font-weight: bold;">{subject}</td>
            <td style="padding: 12px; color: #7f8c8d; font-size: 12px;">{snippet}...</td>
        </tr>
        """
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">📧 Resumen de Emails</h2>
        <p style="color: #7f8c8d; font-size: 14px;">
            Período: 12:00 PM - 6:00 PM | {datetime.now().strftime('%d/%m/%Y')}<br>
            Total: {len(emails)} correos encontrados
        </p>
        
        <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <thead style="background: #2c3e50; color: white;">
                <tr>
                    <th style="padding: 12px; text-align: left;">De</th>
                    <th style="padding: 12px; text-align: left;">Asunto</th>
                    <th style="padding: 12px; text-align: left;">Vista previa</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        
        <p style="color: #95a5a6; font-size: 12px; margin-top: 20px;">
            Enviado automáticamente por Conti Bot
        </p>
    </div>
    """
    return html

def send_summary_email(emails):
    """Envía el resumen por email"""
    
    html_content = generate_html_summary(emails)
    
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    msg['Subject'] = f"📧 Resumen de Emails - {datetime.now().strftime('%d/%m/%Y')} (12pm-6pm)"
    
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Resumen enviado: {len(emails)} emails encontrados")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False

def main():
    print(f"📧 Email Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Obtener emails
    print("📥 Obteniendo correos de las últimas 6 horas...")
    emails = get_emails_from_gmail()
    
    print(f"📬 {len(emails)} correos encontrados")
    
    # Mostrar en consola
    for i, email in enumerate(emails[:10], 1):
        print(f"  {i}. {email.get('subject', 'Sin asunto')[:50]}")
    
    if len(emails) > 10:
        print(f"  ... y {len(emails) - 10} más")
    
    # Enviar resumen
    if emails:
        send_summary_email(emails)
    else:
        # Enviar aunque sea vacío
        send_summary_email([])

if __name__ == '__main__':
    main()
