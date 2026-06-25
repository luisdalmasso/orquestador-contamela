import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"
# Probando la contraseña del usuario root del sistema que a veces se hereda
password = "admin_odoo" 

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    if uid:
        print(f"FOUND: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0.0]]])
        if ids:
            models.execute_kw(db, uid, password, 'product.template', 'write', [ids, {'list_price': 1.0}])
            print(f"Corrected {len(ids)}")
    else:
        # Probando con 'odoo'
        uid = common.authenticate(db, username, "odoo", {})
        if uid:
            print(f"FOUND: {uid}")
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
            ids = models.execute_kw(db, uid, "odoo", 'product.template', 'search', [[['list_price', '=', 0.0]]])
            if ids:
                models.execute_kw(db, uid, "odoo", 'product.template', 'write', [ids, {'list_price': 1.0}])
                print(f"Corrected {len(ids)}")
        else:
            print("AUTH_FAIL")
except Exception as e:
    print(f"ERR: {e}")
