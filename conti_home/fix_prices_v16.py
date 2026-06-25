import xmlrpc.client
import os

url = "https://resto.contamela.com"
tenant_id = "resto"
db = "resto"
username = "resto"
password = "resto"

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        super().send_headers(connection, headers)

print(f"--- Iniciando corrección final de precios ---")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Autenticado (UID: {uid})")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18: product.product.lst_price no es persistente (es calculado).
        # Debemos buscar y escribir en product.template.list_price.
        
        # 1. Buscar plantillas con precio 0.0
        template_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0.0]]])
        
        if template_ids:
            print(f"Encontradas {len(template_ids)} plantillas con precio 0. Corrigiendo...")
            res = models.execute_kw(db, uid, password, 'product.template', 'write', [template_ids, {'list_price': 1.0}])
            if res:
                print(f"¡Éxito! Se actualizaron {len(template_ids)} materiales.")
            else:
                print("Error al ejecutar la actualización.")
        else:
            print("No se encontraron materiales con precio 0 en product.template.")
            
        # 2. Verificar si existen variantes con precios específicos (aunque lst_price falle, list_price existe en variantes)
        # En product.product, list_price suele heredar del template o ser sobreescrito.
        # Pero usualmente corregir el template es suficiente para todos los materiales del POS.
            
        print("Proceso completado.")
    else:
        print("Fallo de autenticación.")
except Exception as e:
    print(f"Error: {e}")
