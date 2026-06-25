import xmlrpc.client
import os
import json
from datetime import datetime

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

    # 1. Identificar al Proveedor General
    partners = models.execute_kw(db, uid, password, "res.partner", "search_read",
                                [[["name", "ilike", "Proveedor General"], ["supplier_rank", ">", 0]]], 
                                {"fields": ["id", "name"]})
    
    if not partners:
        partners = models.execute_kw(db, uid, password, "res.partner", "search_read",
                                    [[["supplier_rank", ">", 0]]], 
                                    {"fields": ["id", "name"], "limit": 1})

    vendor_id = partners[0]['id']
    vendor_name = partners[0]['name']

    # Mapeo corregido con nombres exactos de product.product
    to_buy_list = {
        "Mozzarella Fior di Latte": 5000.0,
        "Arroz de Sushi (cocido)": 4900.0,
        "Salsa de Tomate San Marzano": 2300.0,
        "Filet de Salmón Fresco": 2100.0,
        "Champiñones Frescos": 1900.0,
        "Ragú Bolognese": 1400.0,
        "Lechuga Iceberg": 730.0,
        "Cebolla Caramelizada": 530.0,
        "Bacon (panceta ahumada)": 340.0,
        "Queso Cheddar Madurado": 300.0,
        "Parmigiano Reggiano": 300.0,
        "Gorgonzola Dolce": 200.0,
        "Salsa BBQ": 200.0,
        "Mayonesa de Curry": 250.0,
        "Albahaca Fresca": 150.0,
        "Alga Nori": 30.0
    }

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 2. Crear Purchase Order (Presupuesto de Compra)
    po_id = models.execute_kw(db, uid, password, "purchase.order", "create",
                             [{
                                 "partner_id": vendor_id,
                                 "state": "draft",
                                 "date_order": now_str
                             }])

    lines_created = 0
    for product_name, qty in to_buy_list.items():
        products = models.execute_kw(db, uid, password, "product.product", "search_read",
                                    [[["name", "=", product_name]]], {"fields": ["id", "uom_id"]})
        
        if products:
            p_id = products[0]['id']
            uom_id = products[0]['uom_id'][0]
            
            models.execute_kw(db, uid, password, "purchase.order.line", "create",
                             [{
                                 "order_id": po_id,
                                 "product_id": p_id,
                                 "product_qty": qty,
                                 "product_uom": uom_id,
                                 "name": product_name,
                                 "price_unit": 0.0,
                                 "date_planned": now_str
                             }])
            lines_created += 1

    print(f"SUCCESS|{po_id}|{vendor_name}|{lines_created}")

except Exception as e:
    print(f"Error: {e}")
