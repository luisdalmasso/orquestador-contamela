import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"
# Contraseña común en entornos de desarrollo/demo
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print(f"Probando acceso con admin/admin en {url}...")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Autenticado (UID: {uid})")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18: product.product suele ser lo que se usa en el POS
        product_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[['lst_price', '=', 0]]])
        
        if product_ids:
            print(f"Encontrados {len(product_ids)} variantes con precio 0. Actualizando...")
            models.execute_kw(db, uid, password, 'product.product', 'write', [product_ids, {'lst_price': 1.0}])
            print("Variantes actualizadas.")
        else:
            # Reintentar con templates
            template_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
            if template_ids:
                print(f"Encontrados {len(template_ids)} templates con precio 0. Actualizando...")
                models.execute_kw(db, uid, password, 'product.template', 'write', [template_ids, {'list_price': 1.0}])
                print("Templates actualizados.")
            else:
                print("No se encontraron productos con precio 0.")
    else:
        print("Fallo de autenticación.")
except Exception as e:
    print(f"Error: {e}")
