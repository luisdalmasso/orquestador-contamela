import xmlrpc.client
import os

# Configuración confirmada por curl: HTTPS y POST (XML-RPC usa POST)
url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"
password = "admin" # Password default

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

print(f"--- Ejecutando actualización masiva ---")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Conexión establecida. UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18.0: Buscar en product.template
        ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0]]])
        
        if ids:
            print(f"Encontrados {len(ids)} items con precio 0. Corrigiendo...")
            models.execute_kw(db, uid, password, 'product.template', 'write', [ids, {'list_price': 1.0}])
            print(f"Actualización completada: {len(ids)} materiales actualizados.")
        else:
            print("Verificando variantes (product.product)...")
            variant_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[['lst_price', '=', 0]]])
            if variant_ids:
                models.execute_kw(db, uid, password, 'product.product', 'write', [variant_ids, {'lst_price': 1.0}])
                print(f"Actualización completada: {len(variant_ids)} variantes actualizadas.")
            else:
                print("No se detectaron materiales con precio 0.")
    else:
        # Intentar con password 'resto'
        uid = common.authenticate(db, username, "resto", {})
        if uid:
             print(f"Conexión establecida con pwd 'resto'. UID: {uid}")
             models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
             ids = models.execute_kw(db, uid, "resto", 'product.template', 'search', [[['list_price', '=', 0]]])
             if ids:
                 models.execute_kw(db, uid, "resto", 'product.template', 'write', [ids, {'list_price': 1.0}])
                 print(f"Actualizados {len(ids)} items.")
             else:
                 print("Nada que actualizar con pwd 'resto'.")
        else:
            print("Error: Credenciales no válidas para admin en el tenant 'resto'.")
            
except Exception as e:
    print(f"Error crítico: {e}")
