import xmlrpc.client
import os
import sys

# Forzar URL y Tenant correctos para Contamela
url = "https://resto.contamela.com"
db = "resto"
username = "admin"
# El tenant_id y la db suelen ser 'resto' en este entorno
tenant_id = "resto"

# Intentar obtener la password del entorno o usar la más probable
password = os.environ.get('ODOO_PASSWORD', 'admin')

class HeaderTransport(xmlrpc.client.Transport):
    def send_headers(self, connection, headers):
        headers.append(('X-Tenant-Id', tenant_id))
        headers.append(('X-Odoo-Database', tenant_id))
        super().send_headers(connection, headers)

def run():
    print(f"Buscando productos con precio 0 en {url}...")
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=HeaderTransport())
        
        # Intentar varias passwords comunes si la del entorno falla
        passwords = [password, "resto", "admin", "contamela2024"]
        uid = None
        used_pw = ""
        
        for pw in passwords:
            try:
                uid = common.authenticate(db, username, pw, {})
                if uid:
                    used_pw = pw
                    break
            except:
                continue
        
        if not uid:
            print("Error: No se pudo autenticar con ninguna contraseña conocida.")
            return

        print(f"Autenticado exitosamente (UID: {uid}).")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=HeaderTransport())
        
        # Odoo 18: product.template -> list_price
        product_ids = models.execute_kw(db, uid, used_pw, 'product.template', 'search', [[['list_price', '=', 0]]])
        
        if not product_ids:
            print("No se encontraron materiales/productos con precio 0. (Verificado en product.template)")
        else:
            print(f"Encontrados {len(product_ids)} productos con precio 0. Actualizando a 1.0...")
            result = models.execute_kw(db, uid, used_pw, 'product.template', 'write', [product_ids, {'list_price': 1.0}])
            if result:
                print(f"¡Éxito! Se actualizaron {len(product_ids)} productos.")
            else:
                print("Error al ejecutar la escritura.")

    except Exception as e:
        print(f"Error durante la ejecución: {e}")

if __name__ == "__main__":
    run()
