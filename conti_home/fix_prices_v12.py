import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "luisdalmasso@contamela.com" # Basado en el perfil del usuario
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())

try:
    # Probar con 'admin' y 'resto'
    uid = common.authenticate(db, username, "admin", {})
    if not uid:
        uid = common.authenticate(db, username, "resto", {})
    
    if uid:
        print(f"UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        ids = models.execute_kw(db, uid, "admin" if uid else "resto", 'product.template', 'search', [[['list_price', '=', 0.0]]])
        if ids:
            print(f"Update {len(ids)}")
    else:
        print("FAIL")
except:
    print("ERR")
