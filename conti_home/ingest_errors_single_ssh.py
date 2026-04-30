#!/usr/bin/env python3
"""
Script para ingestar errores - UNA sola conexión SSH
"""
import subprocess
import re
import json
from datetime import datetime

SSH_KEY = '/home/conti/.ssh/id_rsa'
VPS_HOST = 'admin_odoo@host.docker.internal'

def run_ssh(cmd, timeout=180):
    result = subprocess.run(
        ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', VPS_HOST, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout, result.stderr, result.returncode

def main():
    print(f"📊 Analizando logs - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    all_errors = []
    containers = ['django-api', 'odoo18', 'n8n', 'redis', 'wppconnect', 
                  'evolution-api', 'chatwoot_web', 'chatwoot_worker', 'cloudflared']
    
    for container in containers:
        print(f"🔍 {container}...", end=" ", flush=True)
        
        cmd = f"docker compose -f /compose/docker-compose.yml logs --since '168h' {container} 2>&1 | head -3000"
        stdout, _, _ = run_ssh(cmd)
        
        errors = []
        for line in stdout.split('\n'):
            if not line.strip():
                continue
            
            ts = re.search(r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})', line)
            fecha = datetime.now().isoformat()
            if ts:
                try:
                    fecha = datetime.strptime(ts.group(1), '%d/%b/%Y:%H:%M:%S').isoformat()
                except:
                    pass
            
            ep = re.search(r'"(GET|POST|PUT|DELETE)\s+(\S+)"', line)
            endpoint = ep.group(2) if ep else None
            
            tipo = None
            detalle = line.strip()[:400]
            
            if re.search(r'killed|KILLED', line, re.I):
                tipo = 'KILLED'
            elif re.search(r'ERROR|CRITICAL|FATAL|Timeout|Exception', line, re.I):
                tipo = 'ERROR'
            elif re.search(r'WARNING|warn', line, re.I):
                tipo = 'WARNING'
            
            if tipo:
                errors.append({
                    'contenedor': container,
                    'aplicacion': container,
                    'tipo_error': tipo,
                    'endpoint': endpoint,
                    'detalle': detalle,
                    'fecha_hora': fecha
                })
        
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
    
    print(f"📝 Total únicos: {len(unique)}")
    
    # Guardar en archivo local
    with open('/tmp/errors.json', 'w') as f:
        json.dump(unique, f)
    
    # Copiar al host (UNA conexión)
    subprocess.run(['scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', 
                   '/tmp/errors.json', f'{VPS_HOST}:/tmp/errors.json'], timeout=30)
    
    # Crear script de inserción
    insert_py = '''#!/usr/bin/env python3
import json
import psycopg2
with open("/tmp/errors.json") as f:
    data = json.load(f)
conn = psycopg2.connect(host="compose-db-1", port=5432, database="odoo", user="odoo", password="odoo")
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
    
    subprocess.run(['scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', 
                   '/tmp/insert.py', f'{VPS_HOST}:/tmp/insert.py'], timeout=30)
    
    # Copiar archivos y ejecutar en django-api (UNA conexión)
    run_ssh("docker compose -f /compose/docker-compose.yml cp /tmp/errors.json django-api:/tmp/errors.json")
    run_ssh("docker compose -f /compose/docker-compose.yml cp /tmp/insert.py django-api:/tmp/insert.py")
    stdout, stderr, code = run_ssh(
        "docker compose -f /compose/docker-compose.yml exec -T django-api python3 /tmp/insert.py"
    )
    
    if code == 0:
        print(f"✅ {stdout.strip()}")
    else:
        print(f"❌ {stderr[:150]}")
    
    print("="*50)

if __name__ == "__main__":
    main()
