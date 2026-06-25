import xmlrpc.client
import os

url = "https://resto.contamela.com"
db = "resto"
username = "resto"
password = "resto"

# En la nube (https) usamos el transporte estándar, 
# la base de datos se resuelve por el dominio o parámetro.
print(f"Connecting to {url}/xmlrpc/2/common...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    print(f"UID: {uid}")
    if uid:
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        # 1. Buscar sesión abierta
        sessions = models.execute_kw(db, uid, password, 
                                    "pos.session", "search_read", 
                                    [[["state", "=", "opened"]]], 
                                    {"fields": ["id", "name"]})
        print(f"SESSIONS: {sessions}")
        
        if sessions:
            session_id = sessions[0]['id']
            # 2. Buscar pedidos
            orders = models.execute_kw(db, uid, password, 
                                      "pos.order", "search_read", 
                                      [[["session_id", "=", session_id]]], 
                                      {"fields": ["id", "name", "table_id", "state", "amount_total"]})
            print(f"ORDERS: {orders}")
        else:
            print("No hay sesiones abiertas.")
except Exception as e:
    print(f"Error: {e}")
