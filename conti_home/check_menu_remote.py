import xmlrpc.client
import os

tenant = os.environ.get("ODOO_TENANT_ID", "resto")
url = f"https://{tenant}.contamela.com"
db = tenant
username = "admin"
password = "admin"

transport = xmlrpc.client.Transport()
# Custom transport to add headers
class HeaderTransport(xmlrpc.client.Transport):
    def __init__(self, tenant_id):
        super().__init__()
        self.tenant_id = tenant_id
    def send_headers(self, connection, headers):
        connection.putheader("X-Tenant-Id", self.tenant_id)
        connection.putheader("X-Odoo-Database", self.tenant_id)
        super().send_headers(connection, headers)

transport = HeaderTransport(tenant)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=transport)
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=transport)

try:
    uid = common.authenticate(db, username, password, {})
    print(f"UID: {uid}")
    if uid:
        products = models.execute_kw(db, uid, password, 'product.template', 'search_read', [
            [["available_in_pos", "=", True], ["sale_ok", "=", True]],
            ["id", "name", "list_price", "description_sale", "categ_id", "image_128"]
        ])
        for p in products:
            print(f"ID: {p['id']}, Name: {p['name']}, Price: {p['list_price']}, Category: {p['categ_id']}")
            if p.get('description_sale'):
                print(f"  Desc: {p['description_sale'][:100]}")
    else:
        print("Auth failed")
except Exception as e:
    print(f"Error: {e}")