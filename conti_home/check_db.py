import xmlrpc.client
import os

url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
print(f"Connecting to {url}/xmlrpc/2/db...")
try:
    db_proxy = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db")
    dbs = db_proxy.list()
    print(f"Databases: {dbs}")
except Exception as e:
    print(f"Error: {e}")
