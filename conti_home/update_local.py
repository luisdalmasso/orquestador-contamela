import xmlrpc.client
import os

# Usamos la configuración interna del contenedor que suele ser la más fiable
url = "http://odoo18:8069"
db = "mendoza" # Basado en test_odoo.py que parece ser la DB real
username = "admin"
password = "admin"

try:
    print(f"Conectando a {url} (DB: {db})...")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Conectado. UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Buscar productos con precio 0
        product_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
        
        if product_ids:
            print(f"Encontrados {len(product_ids)} productos. Actualizando...")
            res = models.execute_kw(db, uid, password, 'product.template', 'write', [product_ids, {'list_price': 1.0}])
            print(f"Resultado: {res}")
        else:
            print("No hay productos con precio 0.")
    else:
        print("Fallo de autenticación local.")
except Exception as e:
    print(f"Error: {e}")
