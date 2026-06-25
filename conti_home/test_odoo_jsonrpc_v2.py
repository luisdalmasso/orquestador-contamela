import requests
import json
import os

url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
db = os.environ.get('ODOO_DB', 'mendoza')
username = os.environ.get('ODOO_USERNAME', 'admin')
password = os.environ.get('ODOO_PASSWORD', 'admin')

headers = {
    'Content-Type': 'application/json',
    'X-Odoo-Database': db
}

payload = {
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "service": "common",
        "method": "version",
        "args": []
    },
    "id": 1
}

print(f"Testing JSON-RPC common/version at {url}/jsonrpc with Header")
try:
    response = requests.post(f"{url}/jsonrpc", data=json.dumps(payload), headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
