import xmlrpc.client
import os
import json

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

    # 1. Definir necesidades (x10 de cada plato con BoM)
    boms = models.execute_kw(db, uid, password, "mrp.bom", "search_read",
                            [], {"fields": ["id", "bom_line_ids"]})
    
    needs = {}
    for bom in boms:
        lines = models.execute_kw(db, uid, password, "mrp.bom.line", "search_read",
                                 [[["bom_id", "=", bom['id']]]], {"fields": ["product_id", "product_qty"]})
        for line in lines:
            prod_id = line['product_id'][0]
            prod_name = line['product_id'][1]
            qty_needed = line['product_qty'] * 10
            if prod_id not in needs:
                needs[prod_id] = {"name": prod_name, "qty": 0}
            needs[prod_id]["qty"] += qty_needed

    # 2. Consultar Stock Actual de esos productos
    product_ids = list(needs.keys())
    stock_data = models.execute_kw(db, uid, password, "product.product", "read",
                                  [product_ids], {"fields": ["qty_available", "uom_id"]})
    
    final_report = []
    for stock in stock_data:
        p_id = stock['id']
        name = needs[p_id]["name"]
        needed = needs[p_id]["qty"]
        available = stock['qty_available']
        uom = stock['uom_id'][1]
        
        to_buy = max(0, needed - available)
        
        final_report.append({
            "name": name,
            "needed": needed,
            "available": available,
            "to_buy": to_buy,
            "uom": uom
        })

    print("STOCK_REPORT_START")
    print(json.dumps(final_report))
    print("STOCK_REPORT_END")

except Exception as e:
    print(f"Error: {e}")
