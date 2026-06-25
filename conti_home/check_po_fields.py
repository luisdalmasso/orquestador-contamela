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

    # Leer campos de purchase.order.line
    fields = models.execute_kw(db, uid, password, "purchase.order.line", "fields_get",
                              [], {"attributes": ["string", "type"]})
    
    for f in sorted(fields.keys()):
        print(f"Field: {f}")

except Exception as e:
    print(f"Error: {e}")
