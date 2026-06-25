import xmlrpc.client
import os

url = "http://host.docker.internal:8069" # Probando vía host bridge
tenant_id = "resto"
db = "resto"
username = "admin"
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print(f"Probando {url}...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    if uid:
        print("OK")
    else:
        print("Fail")
except Exception as e:
    print(f"Error: {e}")
