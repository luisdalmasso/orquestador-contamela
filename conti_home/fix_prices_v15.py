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

print(f"Iniciando corrección masiva para el tenant {tenant_id}...")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"Autenticado exitosamente. UID: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # 1. Corregir templates (product.template)
        template_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '=', 0.0]]])
        if template_ids:
            print(f"Se encontraron {len(template_ids)} plantillas de producto con precio 0. Actualizando...")
            models.execute_kw(db, uid, password, 'product.template', 'write', [template_ids, {'list_price': 1.0}])
            print("Plantillas actualizadas.")
        else:
            print("No se encontraron plantillas con precio 0.")
            
        # 2. Corregir variantes (product.product) por si hay precios específicos
        variant_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[['lst_price', '=', 0.0]]])
        if variant_ids:
            print(f"Se encontraron {len(variant_ids)} variantes de producto con precio 0. Actualizando...")
            models.execute_kw(db, uid, password, 'product.product', 'write', [variant_ids, {'lst_price': 1.0}])
            print("Variantes actualizadas.")
        else:
            print("No se encontraron variantes con precio 0.")
            
        print("Proceso finalizado con éxito.")
    else:
        print("Error crítico: Fallo de autenticación final.")
except Exception as e:
    print(f"Error durante el proceso: {e}")
