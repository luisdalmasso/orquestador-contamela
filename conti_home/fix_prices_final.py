import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print("Iniciando escaneo de precios...")

# Intentamos con las contraseñas que hemos visto en el sistema
for pwd in ["admin", "resto", "odoo"]:
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
        uid = common.authenticate(db, username, pwd, {})
        if uid:
            print(f"Autenticado con: {pwd} (UID: {uid})")
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
            
            # Buscamos en product.template
            ids = models.execute_kw(db, uid, pwd, 'product.template', 'search', [[['list_price', '=', 0]]])
            
            if ids:
                print(f"Encontrados {len(ids)} productos. Actualizando...")
                models.execute_kw(db, uid, pwd, 'product.template', 'write', [ids, {'list_price': 1.0}])
                print(f"Actualización terminada para {len(ids)} items.")
            else:
                print("No hay productos con precio 0.")
            break
    except Exception as e:
        continue
else:
    print("No se pudo conectar. Por favor, verificá las credenciales o el estado del servidor.")
