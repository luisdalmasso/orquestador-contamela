#!/usr/bin/env python3
"""
Script para ingestar errores del contenedor n8n en PostgreSQL
Analiza logs de los últimos 7 días y los carga a la tabla container_errors
"""
import subprocess
import re
import base64
from datetime import datetime

# Configuración SSH
SSH_KEY = '/home/conti/.ssh/id_rsa'
VPS_HOST = 'admin_odoo@host.docker.internal'

# Contenedor a analizar
CONTAINER = 'n8n'

def get_docker_logs(container, since_hours=168):
    """Obtiene logs del contenedor n8n"""
    try:
        cmd = [
            'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
            VPS_HOST,
            f'docker compose -f /compose/docker-compose.yml logs --since \'{since_hours}h\' {container} 2>&1'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            print(f"   ⚠️ Error en comando: {result.stderr[:200]}")
        return result.stdout
    except Exception as e:
        print(f"   ❌ Error obteniendo logs: {e}")
        return ""

def parse_errors(logs, contenedor):
    """Parsea los logs y extrae errores, warnings, killed, timeouts y exceptions"""
    errores = []
    
    lines = logs.split('\n')
    for line in lines:
        if not line.strip():
            continue
        
        # Extraer timestamp de diferentes formatos
        fecha_hora = datetime.now()
        
        # Formato: 2024-01-15T10:30:00.000Z
        ts_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
        if ts_match:
            try:
                fecha_hora = datetime.strptime(ts_match.group(1), '%Y-%m-%dT%H:%M:%S')
            except:
                pass
        else:
            # Formato: 15/Jan/2024:10:30:00
            ts_match = re.search(r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})', line)
            if ts_match:
                try:
                    fecha_hora = datetime.strptime(ts_match.group(1), '%d/%b/%Y:%H:%M:%S')
                except:
                    pass
        
        # Extraer endpoint de requests
        endpoint_match = re.search(r'"(GET|POST|PUT|DELETE|PATCH)\s+(\S+)"', line)
        endpoint = endpoint_match.group(2) if endpoint_match else None
        
        # Detectar tipo de error
        # Prioridad: KILLED > FATAL > ERROR > timeout > exception > WARNING
        tipo_error = None
        detalle = line.strip()[:500]  # Aumentar para capturar más contexto
        
        if re.search(r'\bKILLED\b', line, re.IGNORECASE):
            tipo_error = 'KILLED'
            # Buscar información de workflow/task
            workflow_match = re.search(r'workflow[- ]?id[:\s=]+(\d+)', line, re.IGNORECASE)
            node_match = re.search(r'node["\s:]+([^"\n]+)', line, re.IGNORECASE)
            detail_parts = []
            if workflow_match:
                detail_parts.append(f"Workflow-{workflow_match.group(1)}")
            if node_match:
                detail_parts.append(f"Node: {node_match.group(1).strip()}")
            prefix = " | ".join(detail_parts) if detail_parts else ""
            detalle = f"{prefix} | {line[:300]}" if prefix else line[:300]
            
        elif re.search(r'\bFATAL\b', line, re.IGNORECASE):
            tipo_error = 'FATAL'
            
        elif re.search(r'\bERROR\b', line, re.IGNORECASE):
            tipo_error = 'ERROR'
            
        elif re.search(r'\btimeout\b', line, re.IGNORECASE):
            tipo_error = 'TIMEOUT'
            
        elif re.search(r'\bexception\b', line, re.IGNORECASE):
            tipo_error = 'EXCEPTION'
            
        elif re.search(r'\bWARNING\b|\bwarn\b', line, re.IGNORECASE):
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

def escape_sql_string(s):
    """Escapa correctamente una cadena para SQL usando '' (estándar SQL)"""
    if s is None:
        return "NULL"
    # Reemplazar comillas simples con dos comillas simples
    return s.replace("'", "''")

def insert_errors(errores):
    """Inserta los errores en la base de datos via SSH usando base64"""
    if not errores:
        print("No hay errores para insertar")
        return 0
    
    inserted = 0
    batch_size = 50  # Batch más pequeño para logs largos
    
    for i in range(0, len(errores), batch_size):
        batch = errores[i:i+batch_size]
        values_list = []
        
        for err in batch:
            endpoint = 'NULL' if err['endpoint'] is None else f"'{escape_sql_string(err['endpoint'])}'"
            detalle = escape_sql_string(err['detalle'])
            fecha_str = err['fecha_hora'].strftime('%Y-%m-%d %H:%M:%S')
            
            values_list.append(
                f"('{escape_sql_string(err['contenedor'])}', '{escape_sql_string(err['aplicacion'])}', "
                f"'{escape_sql_string(err['tipo_error'])}', {endpoint}, E'{detalle}', '{fecha_str}', 'PENDIENTE')"
            )
        
        values_str = ",\n".join(values_list)
        
        # Crear SQL
        sql = f"""
INSERT INTO container_errors 
(contenedor, aplicacion, tipo_error, endpoint, detalle, fecha_hora, status)
VALUES 
{values_str};
"""
        # Codificar en base64
        sql_b64 = base64.b64encode(sql.encode('utf-8')).decode('utf-8')
        
        # Ejecutar SQL en el contenedor usando base64 decode
        cmd = [
            'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
            VPS_HOST,
            f'echo "{sql_b64}" | base64 -d | docker compose -f /compose/docker-compose.yml exec -T db psql -U odoo -d odoo'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                inserted += len(batch)
                print(f"   → Insertados batch {i//batch_size + 1}: {inserted}/{len(errores)}")
            else:
                print(f"   ⚠️ Error en batch: {result.stderr[:300] if result.stderr else result.stdout[:300]}")
        except Exception as e:
            print(f"   ❌ Error ejecutando SQL: {e}")
    
    return inserted

def check_table_exists():
    """Verifica si la tabla container_errors existe"""
    sql = "SELECT to_regclass('public.container_errors');"
    cmd = [
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        f'docker compose -f /compose/docker-compose.yml exec -T db psql -U odoo -d odoo -c "{sql}"'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return 'container_errors' in result.stdout
    except:
        return False

def create_table_if_not_exists():
    """Crea la tabla container_errors si no existe"""
    sql = """
    CREATE TABLE IF NOT EXISTS container_errors (
        id SERIAL PRIMARY KEY,
        contenedor VARCHAR(100),
        aplicacion VARCHAR(100),
        tipo_error VARCHAR(50),
        endpoint VARCHAR(500),
        detalle TEXT,
        fecha_hora TIMESTAMP,
        status VARCHAR(20) DEFAULT 'PENDIENTE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_container_errors_fecha ON container_errors(fecha_hora);
    CREATE INDEX IF NOT EXISTS idx_container_errors_tipo ON container_errors(tipo_error);
    CREATE INDEX IF NOT EXISTS idx_container_errors_contenedor ON container_errors(contenedor);
    """
    cmd = [
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        VPS_HOST,
        f'docker compose -f /compose/docker-compose.yml exec -T db psql -U odoo -d odoo -c "{sql}"'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"Error creando tabla: {e}")
        return False

def main():
    print(f"📊 Iniciando análisis de logs de n8n - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar/crear tabla
    print("🔧 Verificando estructura de la tabla...")
    if not check_table_exists():
        print("   Creando tabla container_errors...")
        create_table_if_not_exists()
    
    # Obtener logs de n8n
    print(f"🔍 Obteniendo logs del contenedor {CONTAINER} (últimos 7 días)...")
    logs = get_docker_logs(CONTAINER, since_hours=168)
    
    if not logs:
        print("❌ No se pudieron obtener los logs")
        return
    
    print(f"   → Logs obtenidos: {len(logs)} caracteres")
    
    # Parsear errores
    print("🔍 Analizando errores en los logs...")
    errors = parse_errors(logs, CONTAINER)
    print(f"   → {len(errors)} líneas de error/warning encontradas")
    
    if errors:
        # Agrupar por tipo
        tipo_counts = {}
        for err in errors:
            tipo = err['tipo_error']
            tipo_counts[tipo] = tipo_counts.get(tipo, 0) + 1
        print(f"   → Distribución: {tipo_counts}")
        
        # Eliminar duplicados (mismo tipo + mismo detalle primeros 100 chars)
        unique_errors = []
        seen = set()
        for err in errors:
            key = (err['tipo_error'], err['detalle'][:100])
            if key not in seen:
                seen.add(key)
                unique_errors.append(err)
        
        print(f"📝 Total errores únicos: {len(unique_errors)}")
        
        # Insertar en DB
        inserted = insert_errors(unique_errors)
        print(f"✅ Errores insertados en DB: {inserted}")
    else:
        print("✅ No hay errores nuevos para insertar")
    
    print("="*60)
    print("✅ Proceso completado")

if __name__ == "__main__":
    main()
