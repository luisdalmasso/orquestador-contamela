import xmlrpc.client
import os

url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
db = os.environ.get('ODOO_DB', 'mendoza')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Odoo-Database', db))
        super().send_headers(connection, headers)

print(f"Connecting to {url}/xmlrpc/2/common with Header...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    version = common.version()
    print(f"Odoo Version: {version}")
except Exception as e:
    print(f"Error: {e}")
