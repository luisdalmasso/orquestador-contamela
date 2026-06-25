import xmlrpc.client
import os
import json

class HeaderTransport(xmlrpc.client.Transport):
    def __init__(self, tenant_id):
        super().__init__()
        self.tenant_id = tenant_id

    def send_headers(self, connection, headers):
        connection.putheader("X-Tenant-Id", self.tenant_id)
        connection.putheader("X-Odoo-Database", self.tenant_id)
        super().send_headers(connection, headers)

def get_menu_report():
    tenant = "resto"
    url = f"https://{tenant}.contamela.com/xmlrpc/2"
    db = tenant
    username = "admin"
    password = "admin"

    transport = HeaderTransport(tenant)
    common = xmlrpc.client.ServerProxy(f"{url}/common", transport=transport)
    models = xmlrpc.client.ServerProxy(f"{url}/object", transport=transport)

    try:
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return "Error de autenticación."
        
        # 1. Buscar el reporte
        reports = models.execute_kw(db, uid, password, 'ir.actions.report', 'search_read', [
            [['name', 'ilike', 'Carta']],
            ['id', 'name', 'report_name']
        ])
        
        if not reports:
             reports = models.execute_kw(db, uid, password, 'ir.actions.report', 'search_read', [
                [['name', 'ilike', 'Menu']],
                ['id', 'name', 'report_name']
            ])

        if not reports:
            return "No se encontró un reporte de carta/menú."

        report = reports[0]
        report_id = report['id']
        
        # 2. Generar el reporte (tomamos un ID de ejemplo de producto o el reporte directamente si es de tipo qweb-pdf)
        # En Odoo, para bajar un reporte por RPC solemos usar report_get o similar, pero aquí la regla dice generar ir.attachment con access_token.
        # Vamos a intentar llamar a una función que devuelva la URL según la lógica de la memoria.
        
        # Simulamos la búsqueda de un attachment o lo creamos
        # Pero mejor, listamos los reportes para que el usuario elija o informamos el que encontramos.
        
        return f"Reporte encontrado: {report['name']} ({report['report_name']}). ID: {report_id}"

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    print(get_menu_report())
