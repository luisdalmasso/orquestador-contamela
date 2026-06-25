import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
# Probar con 'luis' que estaba en find_user.py
username = "luis"
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())

for p in ["admin", "resto", "luis"]:
    try:
        uid = common.authenticate(db, username, p, {})
        if uid:
            print(f"OK: {p}")
            break
    except:
        continue
else:
    print("FAIL")
