#!/usr/bin/env python3
"""
Script para ingestar errores de contenedores
Conexión directa al contenedor db (sin SSH)
"""
import subprocess
import re
import json
from datetime import datetime

CONTAINERS = [
    'django-api', 'odoo18', 'n8n', 'redis', 'wppconnect', 
    'evolution-api', 'chatwoot_web', 'chatwoot_worker', 'cloudflared'
]

# Conexión directa al contenedor db
DB_CMD = [
    'docker', 'exec', '-i', 'compose-db-1',
    'psql', '-U', 'odoo', '-d', 'odoo', '-c'
]

def get_docker_logs(container, since_hours=168):
    """Obtiene logs directamente del contenedor"""
    cmd = [
        'docker', 'exec', '-i', f'compose-{container}',
        'sh', '-c', f"docker compose -f /compose/docker-compose.yml logs --since '{since_hours}h' {container} 2>&1 | head -5000"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout
    except Exception as e:
        print(f"Error {container}: {e}")
        return ""

def parse_errors(logs, contenedor):
    errores = []
    for line in logs.split('\n'):
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
        
        tipo = None
        detalle = line.strip()[:400]
        
        if re.search(r'killed|KILLED', line, re.IGNORECASE):
            tipo = 'KILLED'
        elif re.search(r'ERROR|CRITICAL|FATAL|Timeout|Exception', line, re.IGNORECASE):
            tipo = 'ERROR'
        elif re.search(r'WARNING|warn', line, re.IGNORECASE):
            tipo = 'WARNING'
        
        if tipo:
            errores.append({
                'contenedor': contenedor,
                'aplicacion': contenedor,
                'tipo_error': tipo,
                'endpoint': endpoint,
                'detalle': detalle,
                'fecha_hora': fecha_hora
            })
    return errores

def insert_batch(errores):
    """Inserta directamente en el contenedor db"""
    if not errores:
        return 0
    
    # Crear JSON temporal
    json_file = '/tmp/errors_batch.json'
    with open(json_file, 'w') as f:
        json.dump(errores, f)
    
    # Copiar a contenedor db
    subprocess.run(['docker', 'cp', json_file, 'compose-db-1:/tmp/errors.json'], timeout=10)
    
    # Script Python para insertar
    insert_py = '''#!/usr/bin/env python3
import json
import psycopg2

with open("/tmp/errors.json") as f:
    data = json.load(f)

conn = psycopg2.connect(host="localhost", port=5432, database="odoo", user="odoo", password="odoo")
cur = conn.cursor()

for e in data:
    cur.execute("INSERT INTO container_errors (contenedor, aplicacion, tipo_error, endpoint, detalle, fecha_hora, status) VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE')",
        (e["contenedor"], e["aplicacion"], e["tipo_error"], e["endpoint"], e["detalle"], e["fecha_hora"]))

conn.commit()
print(f"Insertados {len(data)}")
cur.close()
conn.close()
'''
    
    with open('/tmp/insert.py', 'w') as f:
        f.write(insert_py)
    
    subprocess.run(['docker', 'cp', '/tmp/insert.py', 'compose-db-1:/tmp/insert.py'], timeout=10)
    
    result = subprocess.run(
        ['docker', 'exec', '-i', 'compose-db-1', 'python3', '/tmp/insert.py'],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode == 0:
        return len(errores)
    else:
        print(f"Error: {result.stderr[:100]}")
        return 0

def main():
    print(f"📊 Analizando logs - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)
    
    all_errors = []
    for container in CONTAINERS:
        print(f"🔍 {container}...", end=" ", flush=True)
        logs = get_docker_logs(container)
        errors = parse_errors(logs, container)
        print(f"{len(errors)}")
        all_errors.extend(errors)
    
    if not all_errors:
        print("✅ Sin errores")
        return
    
    # Deduplicar
    unique, seen = [], set()
    for e in all_errors:
        key = (e['contenedor'], e['tipo_error'], e['detalle'][:40])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    
    print(f"📝 Únicos: {len(unique)}")
    inserted = insert_batch(unique)
    print(f"✅ Insertados: {inserted}")
    print("="*50)

if __name__ == "__main__":
    main()
