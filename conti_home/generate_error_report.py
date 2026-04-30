#!/usr/bin/env python3
"""
Reporte HTML de errores - Enviar por email
"""
import subprocess
import json
from datetime import datetime

def run_ssh(cmd):
    result = subprocess.run(
        ['ssh', '-i', '/home/conti/.ssh/id_rsa', '-o', 'StrictHostKeyChecking=no', 
         'admin_odoo@host.docker.internal', cmd],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout

# Obtener datos
sql = """
SELECT 
    contenedor,
    tipo_error,
    COUNT(*) as total,
    MIN(fecha_hora::date) as desde,
    MAX(fecha_hora::date) as hasta
FROM container_errors 
WHERE fecha_hora >= NOW() - INTERVAL '48 hours'
GROUP BY contenedor, tipo_error 
ORDER BY contenedor, tipo_error;
"""

output = run_ssh(f"docker compose -f /compose/docker-compose.yml exec -T db psql -U odoo -d odoo -t -c \"{sql}\"")

# Parsear datos
html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 5px 0 0 0; opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #343a40; color: white; padding: 12px; text-align: left; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background: #f8f9fa; }
        .error { color: #dc3545; font-weight: bold; }
        .warning { color: #ffc107; font-weight: bold; }
        .killed { color: #6c757d; font-weight: bold; }
        .total { background: #e9ecef; font-weight: bold; }
        .footer { padding: 15px; text-align: center; color: #666; font-size: 12px; background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐛 Reporte de Errores - Últimas 48hs</h1>
            <p>Contamela - """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """</p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Contenedor</th>
                    <th>Tipo</th>
                    <th>Cantidad</th>
                    <th>Período</th>
                </tr>
            </thead>
            <tbody>
"""

total_general = 0
for line in output.strip().split('\n'):
    if '|' in line:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 5 and parts[0]:
            contenedor = parts[0]
            tipo = parts[1]
            cant = int(parts[2])
            desde = parts[3]
            hasta = parts[4]
            total_general += cant
            
            tipo_class = 'error' if tipo == 'ERROR' else ('warning' if tipo == 'WARNING' else 'killed')
            emoji = '🚨' if tipo == 'ERROR' else ('⚠️' if tipo == 'WARNING' else '☠️')
            
            html += f"""
                <tr>
                    <td>{contenedor}</td>
                    <td class="{tipo_class}">{emoji} {tipo}</td>
                    <td>{cant}</td>
                    <td>{desde} al {hasta}</td>
                </tr>
            """

html += f"""
            </tbody>
            <tfoot>
                <tr class="total">
                    <td colspan="2"><strong>TOTAL</strong></td>
                    <td><strong>{total_general}</strong></td>
                    <td></td>
                </tr>
            </tfoot>
        </table>
        
        <div class="footer">
            <p>🐛 Conti - Reporte automático de errores</p>
            <p>Datos extraídos de la tabla container_errors (PostgreSQL)</p>
        </div>
    </div>
</body>
</html>
"""

# Guardar
with open('/tmp/reporte_errores.html', 'w') as f:
    f.write(html)

print("Reporte generado")
print(f"Total errores: {total_general}")
