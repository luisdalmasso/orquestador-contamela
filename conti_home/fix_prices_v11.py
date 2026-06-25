import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
# A veces el usuario admin en Odoo 18 multitenant es el email
username = "admin@contamela.com"
password = "admin"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())

try:
    uid = common.authenticate(db, username, password, {})
    if uid:
        print("OK")
    else:
        # Intentar con password 'resto'
        uid = common.authenticate(db, username, "resto", {})
        if uid:
            print("OK_RESTO")
        else:
            print("FAIL")
except:
    print("ERR")
