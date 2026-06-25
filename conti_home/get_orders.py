import requests
import json
import os

url = os.environ.get('ODOO_URL', 'http://odoo18:8069')
db = "odoo-resto"
username = "admin"  # O el que corresponda
password = "admin"  # O el que corresponda

headers = {
    'Content-Type': 'application/json',
    'X-Odoo-Database': db
}

def call_odoo(service, method, *args):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": service,
            "method": method,
            "args": args
        },
        "id": 1
    }
    response = requests.post(f"{url}/jsonrpc", data=json.dumps(payload), headers=headers)
    return response.json()

# 1. Login para obtener UID
print(f"Login in {db}...")
auth_resp = call_odoo("common", "authenticate", db, username, password, {})
uid = auth_resp.get('result')

if uid:
    print(f"UID: {uid}")
    # 2. Buscar sesión abierta
    sessions = call_odoo("object", "execute_kw", db, uid, password, 
                        "pos.session", "search_read", 
                        [[["state", "=", "opened"]]], 
                        {"fields": ["id", "name"]})
    print(f"SESSIONS: {json.dumps(sessions)}")
    
    if "result" in sessions and sessions["result"]:
        session_id = sessions["result"][0]["id"]
        # 3. Buscar pedidos
        orders = call_odoo("object", "execute_kw", db, uid, password, 
                          "pos.order", "search_read", 
                          [[["session_id", "=", session_id]]], 
                          {"fields": ["id", "name", "table_id", "state", "amount_total"]})
        print(f"ORDERS: {json.dumps(orders)}")
    else:
        print("No hay sesiones abiertas.")
else:
    print(f"Auth failed: {auth_resp}")
