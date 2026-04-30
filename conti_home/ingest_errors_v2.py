#!/usr/bin/env python3
"""
Script para ingestar errores de contenedores - Versión simple
"""
import subprocess
import re
import json
import os
from datetime import datetime

SSH_KEY = '/home/conti/.ssh/id_rsa'
VPS_HOST = 'admin_odoo@host.docker.internal'

CONTAINERS = [
    'django-api', 'odoo18', 'n8n', 'redis', 'wppconnect', 
    'evolution-api', 'chatwoot_web', 'chatwoot_worker', 'cloudflared'
]

def get_docker_logs(container, since_hours=168):
    cmd = [
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        f"docker compose -f /compose/docker-compose.yml logs --since '{since_hours}h' {container} 2>&1"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.stdout

def parse_errors(logs, contenedor):
    errores = []
    lines = logs.split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        ts_match = re.search(r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})', line)
        fecha_hora = datetime.now().isoformat()
        if ts_match:
            try:
                fecha_hora = datetime.strptime(ts_match.group(1), '%d/%b/%Y:%H:%M:%S').isoformat()
            except:
                pass
        
        endpoint_match = re.search(r'"(GET|POST|PUT|DELETE)\s+(\S+)"', line)
        endpoint = endpoint_match.group(2) if endpoint_match else None
        
        tipo_error = None
        detalle = line.strip()[:400]
        
        if re.search(r'killed|KILLED', line, re.IGNORECASE):
            tipo_error = 'KILLED'
        elif re.search(r'ERROR|CRITICAL|FATAL|Timeout|Exception', line, re.IGNORECASE):
            tipo_error = 'ERROR'
        elif re.search(r'WARNING|warn', line, re.IGNORECASE):
            tipo_error = 'WARNING'
        
        if tipo_error:
            errores.append({
                'contenedor': contenedor,
                'aplicacion': contenedor,
                'tipo_error': tipo_error,
                'endpoint': endpoint,
                'detalle': detalle,
                'fecha_hora': fecha_hora
            })
    
    return errores

def main():
    print(f"📊 Analizando logs - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    all_errors = []
    
    for container in CONTAINERS:
        print(f"🔍 {container}...", end=" ")
        logs = get_docker_logs(container)
        errors = parse_errors(logs, container)
        print(f"{len(errors)} errores")
        all_errors.extend(errors)
    
    if not all_errors:
        print("✅ Sin errores")
        return
    
    # Deduplicar
    unique = []
    seen = set()
    for e in all_errors:
        key = (e['contenedor'], e['tipo_error'], e['detalle'][:40])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    
    print(f"\n📝 Total únicos: {len(unique)}")
    
    # Guardar JSON local
    json_file = '/tmp/all_errors.json'
    with open(json_file, 'w') as f:
        json.dump(unique, f)
    
    # Copiar al VPS
    subprocess.run([
        'scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        json_file, f'{VPS_HOST}:/tmp/all_errors.json'
    ], timeout=30)
    
    # Crear script Python en archivo local
    insert_script = '''#!/usr/bin/env python3
import json
import psycopg2

with open("/tmp/all_errors.json") as f:
    data = json.load(f)

conn = psycopg2.connect(host="compose-db-1", port=5432, database="odoo", user="odoo", password="odoo")
cur = conn.cursor()

for e in data:
    cur.execute("INSERT INTO container_errors (contenedor, aplicacion, tipo_error, endpoint, detalle, fecha_hora, status) VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE')",
        (e["contenedor"], e["aplicacion"], e["tipo_error"], e["endpoint"], e["detalle"], e["fecha_hora"]))

conn.commit()
print(f"Insertados {len(data)} errores")
cur.close()
conn.close()
'''
    
    with open('/tmp/insert.py', 'w') as f:
        f.write(insert_script)
    
    # Copiar script al VPS
    subprocess.run([
        'scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        '/tmp/insert.py', f'{VPS_HOST}:/tmp/insert.py'
    ], timeout=30)
    
    # Ejecutar
    result = subprocess.run([
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        'docker compose -f /compose/docker-compose.yml exec -T db python3 /tmp/insert.py'
    ], capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        print(f"✅ {result.stdout.strip()}")
    else:
        print(f"❌ Error: {result.stderr[:200]}")
    
    print("="*50)

if __name__ == "__main__":
    main()
