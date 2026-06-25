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

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())

    # Algunos modelos como 'product.product' tienen 'list_price' heredado del template.
    # Buscamos en 'product.template' (materiales base)
    zero_price_templates = models.execute_kw(db, uid, password, 'product.template', 'search', [[['list_price', '<=', 0.01]]])
    
    if zero_price_templates:
        print(f"Corrigiendo {len(zero_price_templates)} productos en product.template...")
        models.execute_kw(db, uid, password, 'product.template', 'write', [zero_price_templates, {'list_price': 1.0}])
        print("Corrección completada en templates.")
    
    # En Odoo 18, a veces los productos se ven en el POS como product.product.
    # Aunque lst_price no sea stored, 'list_price' en product.product sí puede serlo o usarse para filtros.
    zero_price_variants = models.execute_kw(db, uid, password, 'product.product', 'search', [[['list_price', '<=', 0.01]]])
    
    if zero_price_variants:
        print(f"Corrigiendo {len(zero_price_variants)} variantes en product.product...")
        models.execute_kw(db, uid, password, 'product.product', 'write', [zero_price_variants, {'list_price': 1.0}])
        print("Corrección completada en variantes.")
    else:
        print("No se encontraron más ítems con precio 0.")

except Exception as e:
    print(f"Error: {e}")
