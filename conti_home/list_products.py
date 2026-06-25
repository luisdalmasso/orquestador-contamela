import xmlrpc.client
import os

url = "https://resto.contamela.com"
db = "resto"
username = "resto"
password = "resto"

def get_connection(service):
    return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/{service}")

try:
    common = get_connection("common")
    uid = common.authenticate(db, username, password, {})
    models = get_connection("object")

    # Listar todos los productos para ver nombres
    products = models.execute_kw(db, uid, password, "product.template", "search_read",
                                [], {"fields": ["id", "name"], "limit": 50})
    for p in products:
        print(f"Product: {p['name']}")

except Exception as e:
    print(f"Error: {e}")
