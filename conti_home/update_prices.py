import xmlrpc.client
import os
import sys

# Configuración desde variables de entorno
url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
db = os.environ.get('ODOO_DB', 'mendoza')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')
tenant_id = os.environ.get('ODOO_TENANT_ID', 'resto')

# Clase para incluir el Header de base de datos necesario en Odoo 18 / Multitenant
class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

print(f"--- Iniciando actualización de precios ---")
print(f"URL: {url}")
print(f"DB: {db}")
print(f"Tenant: {tenant_id}")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if not uid:
        print("Error: Autenticación fallida.")
        sys.exit(1)
        
    print(f"Autenticado con UID: {uid}")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
    
    # Buscar productos con precio 0 (product.template)
    product_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
    
    if not product_ids:
        print("No se encontraron materiales/productos con precio 0.")
    else:
        print(f"Encontrados {len(product_ids)} productos con precio 0. Actualizando...")
        # Actualizar a 1
        result = models.execute_kw(db, uid, password, 'product.template', 'write', [product_ids, {'list_price': 1}])
        if result:
            print(f"Éxito: Se actualizaron {len(product_ids)} productos a precio 1.")
        else:
            print("Error al ejecutar la actualización en Odoo.")
            
except Exception as e:
    print(f"Error de protocolo o conexión: {e}")
    sys.exit(1)
