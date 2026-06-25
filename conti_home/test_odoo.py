import xmlrpc.client
import os

url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
db = os.environ.get('ODOO_DB', 'mendoza')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')

print(f"Connecting to {url}/xmlrpc/2/common...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    version = common.version()
    print(f"Odoo Version: {version}")
    
    uid = common.authenticate(db, username, password, {})
    print(f"Authenticated UID: {uid}")
    
    if uid:
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        # List items in inventory (stock.quant or stock.lot)
        stock = models.execute_kw(db, uid, password, 'stock.quant', 'search_read', [[]], {'limit': 5})
        print(f"Stock Sample: {stock}")
    else:
        print("Failed to authenticate.")
except Exception as e:
    print(f"Error: {e}")
