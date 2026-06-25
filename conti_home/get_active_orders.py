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

    # 1. Buscar sesión activa
    sessions = models.execute_kw(db, uid, password, 'pos.session', 'search_read', 
                               [[['state', '=', 'opened']]], {'fields': ['id', 'name'], 'limit': 1})
    
    if not sessions:
        print("No hay ninguna sesión de POS abierta actualmente.")
        exit(0)
    
    session_id = sessions[0]['id']
    print(f"Sesión activa: {sessions[0]['name']}")

    # 2. Buscar pedidos en borrador (comandas abiertas en mesas)
    orders = models.execute_kw(db, uid, password, 'pos.order', 'search_read',
                              [[['session_id', '=', session_id], ['state', '=', 'draft']]],
                              {'fields': ['id', 'name', 'table_id', 'amount_total', 'lines']})

    if not orders:
        print("No hay pedidos activos en las mesas en este momento.")
    else:
        print(f"Pedidos activos ({len(orders)}):")
        for order in orders:
            table_name = order['table_id'][1] if order['table_id'] else "Sin mesa"
            print(f"- {table_name}: {order['name']} | Total: ${order['amount_total']}")
            
            # Obtener detalle de las líneas
            if order['lines']:
                lines = models.execute_kw(db, uid, password, 'pos.order.line', 'read',
                                         [order['lines']], {'fields': ['product_id', 'qty', 'price_unit']})
                for line in lines:
                    print(f"  > {line['qty']}x {line['product_id'][1]}")

except Exception as e:
    print(f"Error: {e}")
