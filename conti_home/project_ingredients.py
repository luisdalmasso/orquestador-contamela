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

    # 1. Obtener la BoM (Lista de Materiales) de todos los productos de comida
    # Primero buscamos productos que sean de comida (categoría 'Food' o similar)
    food_categs = models.execute_kw(db, uid, password, "product.category", "search",
                                   [[["name", "ilike", "Food"]]])
    
    # Buscamos productos que tengan BoM
    boms = models.execute_kw(db, uid, password, "mrp.bom", "search_read",
                            [], {"fields": ["id", "product_tmpl_id", "bom_line_ids"]})
    
    projection = {}
    
    for bom in boms:
        product_name = bom['product_tmpl_id'][1]
        bom_id = bom['id']
        
        # 2. Leer las líneas de la BoM (ingredientes)
        lines = models.execute_kw(db, uid, password, "mrp.bom.line", "search_read",
                                 [[["bom_id", "=", bom_id]]], {"fields": ["product_id", "product_qty", "product_uom_id"]})
        
        for line in lines:
            ingredient_name = line['product_id'][1]
            qty_per_unit = line['product_qty']
            uom = line['product_uom_id'][1]
            
            # Proyectar x10 unidades de cada plato
            total_needed = qty_per_unit * 10
            
            if ingredient_name not in projection:
                projection[ingredient_name] = {"qty": 0, "uom": uom}
            
            projection[ingredient_name]["qty"] += total_needed

    # 3. Formatear salida
    if projection:
        print("INGREDIENTS_START")
        for ing, data in projection.items():
            print(f"{ing}: {data['qty']} {data['uom']}")
        print("INGREDIENTS_END")
    else:
        print("NO_BOMS_FOUND")

except Exception as e:
    print(f"Error: {e}")
