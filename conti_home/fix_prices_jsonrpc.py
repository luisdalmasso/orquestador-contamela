import requests
import json
import os

url = "https://resto.contamela.com/jsonrpc"
tenant_id = "resto"
db = "resto"
username = "admin"
# Probamos con 'resto' que estaba en otros scripts
password = "resto"

def json_rpc(url, method, params):
    data = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-Id": tenant_id,
        "X-Odoo-Database": db
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

print(f"Intentando autenticación JSON-RPC en {url}...")
try:
    auth_res = json_rpc(url, "call", {
        "service": "common",
        "method": "authenticate",
        "args": [db, username, password, {}]
    })
    
    uid = auth_res.get("result")
    if uid:
        print(f"Autenticado (UID: {uid}). Buscando productos...")
        
        search_res = json_rpc(url, "call", {
            "service": "object",
            "method": "execute_kw",
            "args": [db, uid, password, "product.template", "search", [[["list_price", "=", 0]]]]
        })
        
        product_ids = search_res.get("result", [])
        if product_ids:
            print(f"Encontrados {len(product_ids)} productos con precio 0. Actualizando...")
            update_res = json_rpc(url, "call", {
                "service": "object",
                "method": "execute_kw",
                "args": [db, uid, password, "product.template", "write", [product_ids, {"list_price": 1.0}]]
            })
            print(f"Resultado actualización: {update_res.get('result')}")
        else:
            print("No se encontraron productos con precio 0.")
    else:
        print(f"Fallo de autenticación. Respuesta: {auth_res}")
except Exception as e:
    print(f"Error: {e}")
