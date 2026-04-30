#!/usr/bin/env python3
"""
Script para ingestar errores de contenedores en PostgreSQL
Analiza logs de los últimos 7 días y los carga a la tabla container_errors
"""
import subprocess
import re
import json
from datetime import datetime

# Configuración SSH
SSH_KEY = '/home/conti/.ssh/id_rsa'
VPS_HOST = 'admin_odoo@host.docker.internal'

# Contenedores a analizar
CONTAINERS = [
    'django-api', 'odoo18', 'n8n', 'redis', 'wppconnect', 
    'evolution-api', 'chatwoot_web', 'chatwoot_worker', 'cloudflared'
]

def get_docker_logs(container, since_hours=168):
    """Obtiene logs del contenedor"""
    try:
        cmd = [
            'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
            VPS_HOST,
            f'docker compose -f /compose/docker-compose.yml logs --since \'{since_hours}h\' {container} 2>&1'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout
    except Exception as e:
        print(f"Error obteniendo logs de {container}: {e}")
        return ""

def parse_errors(logs, contenedor):
    """Parsea los logs y extrae errores, warnings y killed"""
    errores = []
    lines = logs.split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        # Extraer timestamp
        ts_match = re.search(r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})', line)
        fecha_hora = datetime.now()
        if ts_match:
            try:
                fecha_hora = datetime.strptime(ts_match.group(1), '%d/%b/%Y:%H:%M:%S')
            except:
                pass
        
        # Extraer endpoint
        endpoint_match = re.search(r'"(GET|POST|PUT|DELETE)\s+(\S+)"', line)
        endpoint = endpoint_match.group(2) if endpoint_match else None
        
        # Detectar tipo de error
        tipo_error = None
        detalle = line.strip()[:500]  # Limitar longitud
        
        if re.search(r'killed|KILLED', line, re.IGNORECASE):
            tipo_error = 'KILLED'
            task_match = re.search(r"Task[- ]?(\d+)", line, re.IGNORECASE)
            detalle = f"Task-{task_match.group(1) if task_match else '?'}"
        elif re.search(r'ERROR|CRITICAL|FATAL|Timeout|Exception|NameError', line, re.IGNORECASE):
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
                'fecha_hora': fecha_hora.isoformat()
            })
    
    return errores

def insert_errors(errores):
    """Inserta los errores en la base de datos via archivo temporal"""
    if not errores:
        print("No hay errores para insertar")
        return 0
    
    # Guardar errores en archivo JSON temporal
    json_file = '/tmp/errors.json'
    with open(json_file, 'w') as f:
        json.dump(errores, f)
    
    # Copiar al VPS
    subprocess.run([
        'scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        json_file, f'{VPS_HOST}:/tmp/errors.json'
    ], timeout=30)
    
    # Insertar desde el VPS usando Python
    insert_sql = f"""
import json
import psycopg2

with open('/tmp/errors.json') as f:
    errores = json.load(f)

conn = psycopg2.connect(
    host='compose-db-1',
    port=5432,
    database='odoo',
    user='odoo',
    password='odoo'
)
cur = conn.cursor()

for err in errores:
    cur.execute(
        \"\"\"
        INSERT INTO container_errors 
        (contenedor, aplicacion, tipo_error, endpoint, detalle, fecha_hora, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE')
        \"\"\",
        (
            err['contenedor'],
            err['aplicacion'],
            err['tipo_error'],
            err['endpoint'],
            err['detalle'][:500],
            err['fecha_hora']
        )
    )

conn.commit()
print(f'Insertados {{len(errores)}} errores')
cur.close()
conn.close()
"""
    
    # Escribir script en VPS
    subprocess.run([
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        f'echo "{insert_sql.replace(chr(34), chr(92)+chr(34))}" > /tmp/insert_errors.py'
    ], timeout=30)
    
    # Ejecutar
    result = subprocess.run([
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        'docker compose -f /compose/docker-compose.yml exec -T db python3 /tmp/insert_errors.py'
    ], capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        print(f"✅ Insertados {len(errores)} errores")
        return len(errores)
    else:
        print(f"Error: {result.stderr[:200]}")
        return 0

def main():
    print(f"📊 Iniciando análisis de logs - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    all_errors = []
    
    for container in CONTAINERS:
        print(f"🔍 Analizando {container}...")
        logs = get_docker_logs(container)
        errors = parse_errors(logs, container)
        print(f"   → {len(errors)} errores encontrados")
        all_errors.extend(errors)
    
    print(f"\n📝 Total errores encontrados: {len(all_errors)}")
    
    if all_errors:
        # Eliminar duplicados
        unique_errors = []
        seen = set()
        for err in all_errors:
            key = (err['contenedor'], err['tipo_error'], err['detalle'][:50])
            if key not in seen:
                seen.add(key)
                unique_errors.append(err)
        
        print(f"📝 Total errores únicos: {len(unique_errors)}")
        
        inserted = insert_errors(unique_errors)
        print(f"✅ Errores insertados en DB: {inserted}")
    else:
        print("✅ No hay errores nuevos")
    
    print("="*60)
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
