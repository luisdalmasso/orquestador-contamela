import xmlrpc.client
import os
import sys

# La URL correcta suele ser /xmlrpc/2/common directamente o sin el 2 si es versión vieja, 
# pero el 404 sugiere que la ruta base o el puerto no responden ahí.
# Intentemos con la URL base directa y el transport con el tenant.

url = "http://odoo18:8069"
db = os.environ.get('ODOO_DB', 'mendoza')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')
tenant_id = os.environ.get('ODOO_TENANT_ID', 'resto')

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        # En Odoo 18 con proxy multitenant, a veces el header es 'X-Tenant-Id'
        headers.append(('X-Tenant-Id', tenant_id))
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

print(f"Probando conexión a {url}...")

try:
    # Intentar autenticar
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(tenant_id, username, password, {}) # Usar tenant_id como DB name también
    
    if not uid:
        # Reintentar con db 'mendoza' por si el tenant es solo para el routing
        uid = common.authenticate(db, username, password, {})
        
    if uid:
        print(f"Autenticado con UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Buscar en product.product (variantes) que es lo que suele usarse en el POS
        product_ids = models.execute_kw(db if not uid else tenant_id, uid, password, 'product.product', 'search', [[['lst_price', '=', 0]]])
        
        if not product_ids:
            # Reintentar con product.template y list_price
            product_ids = models.execute_kw(tenant_id, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
            model = 'product.template'
            field = 'list_price'
        else:
            model = 'product.product'
            field = 'lst_price'

        if product_ids:
            print(f"Encontrados {len(product_ids)} items en {model} con precio 0.")
            res = models.execute_kw(tenant_id, uid, password, model, 'write', [product_ids, {field: 1.0}])
            print(f"Resultado actualización: {res}")
        else:
            print("No se encontraron productos con precio 0 en ningún modelo.")
    else:
        print("No se pudo autenticar.")

except Exception as e:
    print(f"Fallo: {e}")
