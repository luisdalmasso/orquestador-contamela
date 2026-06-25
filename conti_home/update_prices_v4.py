import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
username = "admin"
password = "resto" # Encontrada en otros scripts como create_purchase_order.py

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print(f"Intentando con password 'resto' en {url}...")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(tenant_id, username, password, {})
    
    if uid:
        print(f"¡Autenticado! UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Buscar en product.template productos con precio 0
        product_ids = models.execute_kw(tenant_id, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
        
        if product_ids:
            print(f"Encontrados {len(product_ids)} productos con precio 0. Actualizando...")
            res = models.execute_kw(tenant_id, uid, password, 'product.template', 'write', [product_ids, {'list_price': 1.0}])
            print(f"Proceso finalizado. Resultado: {res}")
        else:
            print("No se encontraron productos con precio 0.")
    else:
        print("Fallo de autenticación con 'resto'.")
except Exception as e:
    print(f"Error: {e}")
