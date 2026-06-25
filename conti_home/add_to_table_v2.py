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
    tables = models.execute_kw(db, uid, password, "restaurant.table", "search_read",
                              [[["table_number", "=", 103]]], {"fields": ["id", "display_name"]})
    
    # 2. Buscar Producto Pizza Margherita
    products = models.execute_kw(db, uid, password, "product.template", "search_read",
                                [[["name", "=", "Pizza Margherita"]]], {"fields": ["id", "name", "list_price"]})

    if tables and products:
        table_id = tables[0]['id']
        template_id = products[0]['id']
        price_unit = products[0]['list_price']
        
        variant = models.execute_kw(db, uid, password, "product.product", "search_read",
                                   [[["product_tmpl_id", "=", template_id]]], {"fields": ["id"]})
        
        if variant:
            product_id = variant[0]['id']
            sessions = models.execute_kw(db, uid, password, "pos.session", "search_read",
                                        [[["state", "=", "opened"]]], {"fields": ["id", "config_id"]})
            
            if sessions:
                session_id = sessions[0]['id']
                
                # Buscar pedido draft
                orders = models.execute_kw(db, uid, password, "pos.order", "search_read",
                                          [[["table_id", "=", table_id], ["state", "=", "draft"], ["session_id", "=", session_id]]], 
                                          {"fields": ["id"]})
                
                if orders:
                    order_id = orders[0]['id']
                else:
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
                
                # Agregar línea con subtotales (Odoo POS los requiere en create por API)
                # price_subtotal = price_unit * qty
                qty = 1
                price_subtotal = price_unit * qty
                price_subtotal_incl = price_subtotal # Asumimos sin impuestos por ahora o que están incluidos
                
                line_id = models.execute_kw(db, uid, password, "pos.order.line", "create",
                                           [{
                                               "order_id": order_id,
                                               "product_id": product_id,
                                               "qty": qty,
                                               "price_unit": price_unit,
                                               "price_subtotal": price_subtotal,
                                               "price_subtotal_incl": price_subtotal_incl,
                                               "name": f"{products[0]['name']} (1)"
                                           }])
                
                # Actualizar el total del pedido
                models.execute_kw(db, uid, password, "pos.order", "write",
                                 [[order_id], {
                                     "amount_total": price_subtotal_incl,
                                     "amount_tax": 0
                                 }])
                
                print("SUCCESS")
except Exception as e:
    print(f"Error: {e}")
