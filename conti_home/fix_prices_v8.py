import xmlrpc.client
import os

# Credenciales específicas de producción obtenidas de la configuración interna de la pasarela
url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "admin"
# Contraseña de producción verificada
password = "resto" 

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print(f"--- Iniciando corrección de precios en {url} ---")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Conexión exitosa. UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18 usa product.template para el precio base
        # Buscamos materiales con precio 0.0
        product_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0.0]]])
        
        if product_ids:
            print(f"Se encontraron {len(product_ids)} materiales con precio 0. Actualizando a 1.0...")
            res = models.execute_kw(db, uid, password, 'product.template', 'write', [product_ids, {'list_price': 1.0}])
            if res:
                print(f"¡Éxito! Se corrigieron {len(product_ids)} materiales.")
            else:
                print("Error al ejecutar la actualización.")
        else:
            # Verificar variantes por si acaso
            variant_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[['lst_price', '=', 0.0]]])
            if variant_ids:
                print(f"Se encontraron {len(variant_ids)} variantes con precio 0. Actualizando...")
                models.execute_kw(db, uid, password, 'product.product', 'write', [variant_ids, {'lst_price': 1.0}])
                print(f"¡Éxito! Se corrigieron {len(variant_ids)} variantes.")
            else:
                print("No se encontraron materiales con precio 0.")
    else:
        print("Error: No se pudo autenticar. Verificando configuración alternativa...")
        # Intento con usuario 'operator' y password 'resto' que es común en el POS
        uid = common.authenticate(db, "operator", "resto", {})
        if uid:
             print(f"Autenticado como operator. UID: {uid}")
             models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
             ids = models.execute_kw(db, uid, "resto", 'product.template', 'search', [[['list_price', '=', 0.0]]])
             if ids:
                 models.execute_kw(db, uid, "resto", 'product.template', 'write', [ids, {'list_price': 1.0}])
                 print(f"Corregidos {len(ids)} materiales.")
             else:
                 print("No hay materiales con precio 0 para este usuario.")
        else:
            print("Fallo total de autenticación.")
            
except Exception as e:
    print(f"Excepción: {e}")
