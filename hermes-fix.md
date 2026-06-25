# Diagnóstico y Plan de Acción: Fallo de Conexión MCP en Agente Hermes (Perfil `resto`)

Este documento presenta un diagnóstico detallado del porqué el agente Hermes (`resto` profile) ha dejado de conectarse a las herramientas de MCP de Odoo, basándose **exclusivamente** en el análisis de logs y configuraciones recopilados el día de hoy, **Lunes 8 de Junio de 2026**.

---

## 1. Resumen Ejecutivo
El fallo de conexión del perfil `resto` del agente Hermes con las herramientas del MCP tiene **dos causas raíz técnicas independientes**:
1. **Filtro de base de datos de Odoo (`dbfilter`):** El host configurado en la cabecera `Host` del perfil `resto` (`odoo18:8072`) no es reconocido por Odoo como una base de datos válida bajo su configuración de filtrado (`dbfilter = ^%d$`), lo que hace que Odoo rechace las peticiones con un código de estado `404 Not Found`.
2. **Conflicto de Transporte de MCP (SSE vs HTTP):** El perfil `resto` utiliza `transport: sse` (Server-Sent Events) mientras que otros perfiles funcionales (como `mendoza`) utilizan `transport: http`. El cliente SSE de Python valida estrictamente que el origen del endpoint de envío coincida con el de conexión, arrojando un error de origen cruzado (`ValueError: Endpoint origin does not match connection origin`) al ser accedido mediante Nginx/Docker en modo reverso.

---

## 2. Diagnóstico Técnico Detallado

### Causa Raíz A: Cabecera `Host` y el Filtro de BD en Odoo (`dbfilter`)
Al revisar la configuración de Odoo en `/compose/config/odoo.conf` hoy, se observa la siguiente directiva activa:
```ini
dbfilter = ^%d$
```
Esta expresión regular significa que Odoo filtra y selecciona de manera estricta la base de datos basándose en el **subdominio** (la parte más a la izquierda) que recibe en la cabecera `Host` del request HTTP:
* Si llega un request con `Host: mendoza.contamela.com`, el subdominio es `mendoza`. Odoo busca la base de datos `mendoza` (existe), y procesa el `/mcp` con éxito.
* Sin embargo, el perfil `resto` de Hermes en su archivo de configuración `/contenedores/conti-backend/app/hermes_profiles/contihome/profiles/resto/config.yaml` tiene configurado lo siguiente:
  ```yaml
  odoo_mcp:
    url: http://odoo18:8072/mcp
    transport: sse
    headers:
      Host: odoo18:8072
      Authorization: Bearer ${CONTI_MCP_API_KEY}
      X-Odoo-Database: ${ODOO_TENANT_ID}
      X-Mesa-Id: ${MESA_ID}
  ```
  La cabecera `Host` enviada es `odoo18:8072`. El subdominio extraído por Odoo es `odoo18`.
  Odoo busca una base de datos llamada `odoo18`. Como esa base de datos no existe (las bases de datos reales son `mendoza`, `resto`, `nudo`, `demo`, `odoo`), Odoo **no logra determinar la base de datos correspondiente** (se registra en logs como base de datos `?`) y responde con un error **`404 NOT FOUND`** para la ruta `/mcp` (ya que los controladores de MCP sólo se registran si hay una base de datos cargada que tenga el módulo correspondiente instalado).

Los logs del contenedor `odoo18` confirman exactamente este comportamiento hoy:
```
2026-06-08 10:49:53,232 44 INFO ? longpolling: 172.18.0.7 - - [2026-06-08 10:49:53] "GET /mcp HTTP/1.1" 404 423 0.000844 
```
*(Nótese el `INFO ?` indicando que Odoo no pudo asociar la petición a ninguna base de datos debido a que recibió `Host: odoo18:8072`)*.

---

### Causa Raíz B: Validación de Origen en el Cliente SSE de MCP
En `errors.log` del agente Hermes, se observan múltiples fallos de este tipo:
```
ValueError: Endpoint origin does not match connection origin: http://resto.contamela.com/mcp?session_id=172b4e75-405a-4c0b-9297-e5f167942daf
```
El cliente de MCP en Python (SDK estándar de Anthropic/Model Context Protocol) tiene una validación estricta de seguridad en su transporte SSE (`mcp.client.sse`):
* El cliente abre el SSE mediante una petición inicial `GET` usando la URL local interna `http://127.0.0.1:9001/mcp/sse` o `http://odoo18:8072/mcp`.
* El servidor responde enviando un evento de inicialización que contiene la URL donde deben enviarse los mensajes `POST` subsiguientes (que Nginx / el proxy reescribe a su URL pública `http://resto.contamela.com/mcp`).
* El cliente de Python detecta que el origen de conexión (`http://127.0.0.1` u `http://odoo18`) **no coincide** con el origen público retornado por la redirección del proxy (`http://resto.contamela.com`). Al haber una discrepancia de orígenes, interrumpe la comunicación arrojando el error `ValueError: Endpoint origin does not match connection origin`.

---

### Causa Raíz C: Fallos de conexión con `contibackend`
El perfil `resto` tiene configurado el mcp de `contibackend` de la siguiente forma:
```yaml
  contibackend:
    url: http://127.0.0.1:9001/mcp/sse
    transport: sse
```
Esto genera dos problemas de conexión dentro del entorno Docker:
1. Al estar utilizando `transport: sse` con un puerto expuesto localmente bajo proxy, sufre el mismo error de `Endpoint origin does not match connection origin` mencionado anteriormente.
2. `127.0.0.1` apunta al propio contenedor de `conti-backend`. Aunque el gateway levanta en `0.0.0.0:9001` y debería estar accesible, cualquier redirección de Nginx externa que intente devolver llamadas públicas mediante la red interna de Docker fallará si hay validación estricta de transporte.

En los perfiles estables y que funcionan correctamente (como `mendoza` y `odoo-mendoza`), se utiliza el transporte de tipo **`http`** puro en lugar de `sse`, evitando por completo la validación cruzada de origen del cliente SSE:
```yaml
  contibackend:
    url: http://localhost:9001/mcp
    transport: http
```

---

## 3. Plan de Acción Recomendado (Paso a Paso)

Para solucionar el problema sin comprometer el aislamiento de subdominios, se deben aplicar los siguientes cambios de configuración de manera quirúrgica:

### Paso 1: Corregir las Cabeceras `Host` y el Transporte en el Perfil `resto`
Modificar el archivo `/contenedores/conti-backend/app/hermes_profiles/contihome/profiles/resto/config.yaml` de la siguiente manera:

1. **Cambiar el transporte de `sse` a `http`** para evitar el error de origen cruzado en entornos reverse-proxied.
2. **Corregir la cabecera `Host`** para que coincida con el subdominio de la base de datos `resto` en Odoo, permitiendo que la directiva `dbfilter = ^%d$` asocie la petición correctamente.

**Configuración propuesta para `odoo_mcp`:**
```yaml
  odoo_mcp:
    url: http://odoo18:8072/mcp
    transport: http
    headers:
      Host: resto.contamela.com
      Authorization: Bearer ${CONTI_MCP_API_KEY}
      X-Odoo-Database: ${ODOO_TENANT_ID}
      X-Mesa-Id: ${MESA_ID}
```

### Paso 2: Ajustar la Configuración de `contibackend` en el Perfil `resto`
En el mismo archivo `resto/config.yaml`, alinear la definición de `contibackend` con el formato HTTP robusto utilizado en `mendoza/config.yaml` para saltar las restricciones de SSE:

**Configuración propuesta para `contibackend`:**
```yaml
  contibackend:
    url: http://localhost:9001/mcp
    transport: http
```

### Paso 3: Reiniciar el Agente Hermes para aplicar los cambios
Una vez guardadas las modificaciones en `config.yaml`, se debe reiniciar el contenedor o el proceso de Hermes para que cargue la nueva configuración.
```bash
docker compose -f /contenedores/conti-backend/docker-compose.conti.yml restart conti-backend
```

---
*Diagnóstico elaborado de forma segura e independiente, respetando la instrucción de no modificar código ni configuraciones en este turno.*
