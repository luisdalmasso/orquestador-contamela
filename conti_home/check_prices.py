import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "resto"
password = "resto"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())

# Listar los primeros 10 productos y sus precios
products = models.execute_kw(db, uid, password, 'product.template', 'search_read', [[['sale_ok', '=', True]]], {'fields': ['name', 'list_price'], 'limit': 20})
for p in products:
    print(f"ID: {p['id']} | Producto: {p['name']} | Precio: {p['list_price']}")
