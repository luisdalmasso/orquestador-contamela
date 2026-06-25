import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = os.environ.get('ODOO_TENANT_ID', 'resto')
# Probamos con la contraseña que suele estar en los archivos del sistema o por defecto
password = os.environ.get('ODOO_PASSWORD', 'admin')

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
# Intentamos autenticar con 'admin' o buscar el usuario correcto
for user in ['admin', 'luis', 'operator']:
    uid = common.authenticate(tenant_id, user, password, {})
    if uid:
        print(f"Éxito con usuario: {user}, UID: {uid}")
        break
else:
    print("No se encontró usuario válido con la contraseña actual.")
