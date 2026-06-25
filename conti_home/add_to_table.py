import xmlrpc.client
import os

url = "https://resto.contamela.com"
db = "resto"
username = "resto"
password = "resto"

def get_connection(service):
    return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/{service}")

try:
    common = get_connection("common")
    uid = common.authenticate(db, username, password, {})
    models = get_connection("object")

    # 1. Buscar Mesa 103
    # Probamos con table_number o display_name
    tables = models.execute_kw(db, uid, password, "restaurant.table", "search_read",
                              [[["table_number", "=", 103]]], {"fields": ["id", "display_name"]})
    if not tables:
        # Reintento con display_name
        tables = models.execute_kw(db, uid, password, "restaurant.table", "search_read",
                                  [[["display_name", "ilike", "103"]]], {"fields": ["id", "display_name"]})
    
    print(f"TABLES: {tables}")

    # 2. Buscar Producto Pizza Margherita
    products = models.execute_kw(db, uid, password, "product.template", "search_read",
                                [[["name", "ilike", "Pizza Margherita"]]], {"fields": ["id", "name", "list_price"]})
    print(f"PRODUCTS: {products}")

    if tables and products:
        table_id = tables[0]['id']
        template_id = products[0]['id']
        price_unit = products[0]['list_price']
        
        # Obtener el product.product variant
        variant = models.execute_kw(db, uid, password, "product.product", "search_read",
                                   [[["product_tmpl_id", "=", template_id]]], {"fields": ["id"]})
        print(f"VARIANTS: {variant}")
        
        if variant:
            product_id = variant[0]['id']
            
            # 3. Buscar sesión abierta
            sessions = models.execute_kw(db, uid, password, "pos.session", "search_read",
                                        [[["state", "=", "opened"]]], {"fields": ["id", "config_id"]})
            print(f"SESSIONS: {sessions}")
            
            if sessions:
                session_id = sessions[0]['id']
                
                # 4. Buscar pedido draft para esa mesa
                orders = models.execute_kw(db, uid, password, "pos.order", "search_read",
                                          [[["table_id", "=", table_id], ["state", "=", "draft"], ["session_id", "=", session_id]]], 
                                          {"fields": ["id"]})
                print(f"ORDERS: {orders}")
                
                if orders:
                    order_id = orders[0]['id']
                else:
                    # Crear pedido draft
                    # Skill says: session_id, table_id, company_id, amount_tax, amount_total, amount_paid, amount_return
                    # Usamos company_id=1 por defecto o lo buscamos
                    order_id = models.execute_kw(db, uid, password, "pos.order", "create",
                                                [{
                                                    "session_id": session_id,
                                                    "table_id": table_id,
                                                    "amount_tax": 0,
                                                    "amount_total": 0,
                                                    "amount_paid": 0,
                                                    "amount_return": 0,
                                                    "state": "draft"
                                                }])
                    print(f"CREATED ORDER: {order_id}")
                
                # 5. Agregar línea
                line_id = models.execute_kw(db, uid, password, "pos.order.line", "create",
                                           [{
                                               "order_id": order_id,
                                               "product_id": product_id,
                                               "qty": 1,
                                               "price_unit": price_unit,
                                               "name": f"{products[0]['name']} (1)"
                                           }])
                print(f"CREATED LINE: {line_id}")
                
                # Recalcular totales del pedido (opcional pero recomendado)
                # En Odoo POS esto suele ser dinámico, pero por API a veces hay que actualizarlo
                # Intentamos llamar a un método si existe o simplemente informamos
                print("SUCCESS")
            else:
                print("NO_SESSION")
        else:
            print("NO_VARIANT")
    else:
        print("MISSING_DATA")

except Exception as e:
    print(f"Error: {e}")
