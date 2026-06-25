import xmlrpc.client
import os

# Usamos la URL que vimos en ODOO_MCP_URL pero para XML-RPC
url = "http://odoo18:8069"
tenant_id = "resto"
db = "resto"
username = "admin"
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

print(f"Probando {url} con tenant {tenant_id}...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(tenant_id, username, password, {})
    if uid:
        print(f"UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        ids = models.execute_kw(tenant_id, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
        if ids:
            models.execute_kw(tenant_id, uid, password, 'product.template', 'write', [ids, {'list_price': 1.0}])
            print(f"Actualizados {len(ids)}")
        else:
            print("Nada a 0")
    else:
        print("Auth Fail")
except Exception as e:
    print(f"Error: {e}")
