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

    # 1. Mesa 103
    tables = models.execute_kw(db, uid, password, "restaurant.table", "search_read",
                              [[["table_number", "=", 103]]], {"fields": ["id"]})
    
    # 2. Producto Fanta
    products = models.execute_kw(db, uid, password, "product.template", "search_read",
                                [[["name", "ilike", "Fanta"]]], {"fields": ["id", "name", "list_price"]})

    if tables and products:
        table_id = tables[0]['id']
        template_id = products[0]['id']
        price_unit = products[0]['list_price']
        
        variant = models.execute_kw(db, uid, password, "product.product", "search_read",
                                   [[["product_tmpl_id", "=", template_id]]], {"fields": ["id"]})
        
        if variant:
            product_id = variant[0]['id']
            sessions = models.execute_kw(db, uid, password, "pos.session", "search_read",
                                        [[["state", "=", "opened"]]], {"fields": ["id"]})
            
            if sessions:
                session_id = sessions[0]['id']
                
                # 3. Buscar pedido draft actual en la mesa
                orders = models.execute_kw(db, uid, password, "pos.order", "search_read",
                                          [[["table_id", "=", table_id], ["state", "=", "draft"], ["session_id", "=", session_id]]], 
                                          {"fields": ["id", "amount_total"]})
                
                if orders:
                    order_id = orders[0]['id']
                    current_total = orders[0]['amount_total']
                    
                    qty = 1
                    price_subtotal = price_unit * qty
                    
                    # 4. Agregar línea de Fanta
                    models.execute_kw(db, uid, password, "pos.order.line", "create",
                                     [{
                                         "order_id": order_id,
                                         "product_id": product_id,
                                         "qty": qty,
                                         "price_unit": price_unit,
                                         "price_subtotal": price_subtotal,
                                         "price_subtotal_incl": price_subtotal,
                                         "name": f"{products[0]['name']} (1)"
                                     }])
                    
                    # 5. Actualizar total del pedido
                    new_total = current_total + price_subtotal
                    models.execute_kw(db, uid, password, "pos.order", "write",
                                     [[order_id], {"amount_total": new_total}])
                    
                    print(f"SUCCESS|{products[0]['name']}|{new_total}")
                else:
                    print("ERROR_NO_DRAFT_ORDER")
            else:
                print("ERROR_NO_SESSION")
        else:
            print("ERROR_NO_VARIANT")
    else:
        print("ERROR_MISSING_DATA")

except Exception as e:
    print(f"Error: {e}")
