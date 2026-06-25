import xmlrpc.client
import os

class HeaderTransport(xmlrpc.client.Transport):
    def __init__(self, tenant_id):
        super().__init__()
        self.tenant_id = tenant_id

    def send_headers(self, connection, headers):
        connection.putheader("X-Tenant-Id", self.tenant_id)
        connection.putheader("X-Odoo-Database", self.tenant_id)
        super().send_headers(connection, headers)

def get_menu():
    tenant = os.environ.get("ODOO_TENANT_ID", "resto")
    url = f"https://{tenant}.contamela.com/xmlrpc/2"
    db = os.environ.get("ODOO_DB", tenant)
    username = os.environ.get("ODOO_USERNAME", "admin")
    password = os.environ.get("ODOO_PASSWORD", "admin")

    transport = HeaderTransport(tenant)
    common = xmlrpc.client.ServerProxy(f"{url}/common", transport=transport)
    models = xmlrpc.client.ServerProxy(f"{url}/object", transport=transport)

    try:
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return "Error de autenticación."
        
        products = models.execute_kw(db, uid, password, 'product.template', 'search_read', [
            [["available_in_pos", "=", True], ["sale_ok", "=", True]],
            ["name", "list_price"]
        ])
        
        if not products:
            return "No se encontraron productos en la carta."
        
        lines = ["--- CARTA RESTAURANTE ---"]
        for p in products:
            name = p['name']
            if isinstance(name, dict):
                name = name.get('es_AR') or name.get('en_US') or list(name.values())[0]
            lines.append(f"- {name}: ${p['list_price']:.2f}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    print(get_menu())
