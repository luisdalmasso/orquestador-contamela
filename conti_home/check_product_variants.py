import xmlrpc.client
import os
import json
from datetime import datetime

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

    # Listar productos con sus nombres exactos en product.product
    products = models.execute_kw(db, uid, password, "product.product", "search_read",
                                [], {"fields": ["id", "name"], "limit": 100})
    for p in products:
        print(f"ID: {p['id']} | Name: {p['name']}")

except Exception as e:
    print(f"Error: {e}")
