import xmlrpc.client
import os

# Forzamos la URL externa si la interna falla (404 suele ser el proxy de Odoo 18 no ruteando bien por IP interna)
url = "https://resto.contamela.com"
tenant_id = os.environ.get('ODOO_TENANT_ID', 'resto')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

print(f"Conectando a {url} para el tenant: {tenant_id}...")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(tenant_id, username, password, {})
    
    if uid:
        print(f"Autenticado correctamente. UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18 usa product.template para list_price
        product_ids = models.execute_kw(tenant_id, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
        
        if product_ids:
            print(f"Encontrados {len(product_ids)} productos con precio 0. Actualizando a 1...")
            res = models.execute_kw(tenant_id, uid, password, 'product.template', 'write', [product_ids, {'list_price': 1.0}])
            print(f"Actualización completada: {res}")
        else:
            print("No hay productos con precio 0.")
    else:
        print("Fallo de autenticación.")
except Exception as e:
    print(f"Error: {e}")
