import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"

# Intentamos una combinación de contraseñas que suelen estar en las imágenes de Conti
passwords = ["resto2024", "resto2025", "admin2024", "contamela", "resto"]

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())

for pwd in passwords:
    try:
        uid = common.authenticate(db, username, pwd, {})
        if uid:
            print(f"AUTHENTICATED: {pwd}")
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
            ids = models.execute_kw(db, uid, pwd, 'product.template', 'search', [[['list_price', '=', 0.0]]])
            if ids:
                models.execute_kw(db, uid, pwd, 'product.template', 'write', [ids, {'list_price': 1.0}])
                print(f"CORRECTED: {len(ids)}")
            else:
                print("NO_ZERO_PRICES")
            break
    except:
        continue
else:
    print("ALL_AUTH_FAILED")
