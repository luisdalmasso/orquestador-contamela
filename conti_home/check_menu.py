import xmlrpc.client

url = "http://localhost:8069"
db = "postgres"
username = "admin"
password = "admin"

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
print(f"UID: {uid}")

if uid:
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    products = models.execute_kw(db, uid, password, 'product.template', 'search_read', [
        [["available_in_pos", "=", True], ["sale_ok", "=", True]],
        ["id", "name", "list_price", "description_sale", "categ_id", "image_128"]
    ])
    for p in products:
        print(f"ID: {p['id']}, Name: {p['name']}, Price: {p['list_price']}, Category: {p['categ_id']}")
        if p.get('description_sale'):
            print(f"  Desc: {p['description_sale'][:100]}")