from pathlib import Path
import requests
from bs4 import BeautifulSoup
import datetime

def catolico_lecturas_dia(config, args: dict) -> dict:
    """
    Obtiene las lecturas del día para la liturgia católica desde dominicos.org.
    """
    fecha_str = args.get("fecha")
    if fecha_str:
        try:
            fecha = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            fecha = datetime.date.today()
    else:
        fecha = datetime.date.today()

    hoy = datetime.date.today()
    if fecha == hoy:
        url = "https://www.dominicos.org/predicacion/evangelio-del-dia/hoy/lecturas/"
    else:
        url = f"https://www.dominicos.org/predicacion/evangelio-del-dia/{fecha.day:02d}-{fecha.month:02d}-{fecha.year}/"

    def extraer_seccion(soup_obj, titulos_posibles):
        if isinstance(titulos_posibles, str):
            titulos_posibles = [titulos_posibles]

        titulo_tag = None
        for titulo_seccion in titulos_posibles:
            titulo_tag = soup_obj.find("h2", string=lambda text: titulo_seccion in text if text else False)
            if titulo_tag:
                break

        if not titulo_tag:
            return f"{titulos_posibles[0]} no encontrada."

        partes_texto = [f"**{titulo_tag.get_text(strip=True)}**"]
        for elemento_siguiente in titulo_tag.find_next_siblings():
            if elemento_siguiente.name == "h2":
                break
            if elemento_siguiente.name in ["h3", "p"] and elemento_siguiente.get_text(strip=True):
                partes_texto.append(elemento_siguiente.get_text(strip=True))

        return "\n".join(partes_texto)

    def extraer_video_youtube(soup_obj):
        titulo_tag = soup_obj.find("h2", string=lambda text: "Evangelio de hoy en vídeo" in text if text else False)
        if not titulo_tag:
            return None

        video_url = None
        video_titulo = None

        for elemento_siguiente in titulo_tag.find_next_siblings():
            if elemento_siguiente.name == "h2":
                break

            iframe = elemento_siguiente.find("iframe")
            if iframe and iframe.get("src"):
                src = iframe.get("src")
                if "youtube.com/embed/" in src:
                    video_id = src.split("youtube.com/embed/")[-1].split("?")[0]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    break
                if "youtube.com" in src or "youtu.be" in src:
                    video_url = src
                    break

            link = elemento_siguiente.find("a", href=True)
            if link:
                href = link.get("href")
                if "youtube.com" in href or "youtu.be" in href:
                    video_url = href
                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) > 5 and link_text != video_url:
                        video_titulo = link_text
                    break

        if not video_url:
            return None

        resultado = "🎥 **Evangelio de hoy en vídeo**\n"
        if video_titulo:
            resultado += f"**{video_titulo}**\n"
        resultado += f'<a href="{video_url}" target="_blank">Ver en YouTube</a>'
        return resultado

    def extraer_audio_soundcloud(soup_obj):
        titulo_tag = soup_obj.find("h2", string=lambda text: "Evangelio de hoy en audio" in text if text else False)
        if not titulo_tag:
            return None

        audio_url = None
        audio_titulo = None

        for elemento_siguiente in titulo_tag.find_next_siblings():
            if elemento_siguiente.name == "h2":
                break

            iframe = elemento_siguiente.find("iframe")
            if iframe and iframe.get("src"):
                src = iframe.get("src")
                if "soundcloud.com" in src:
                    audio_url = src
                    break

            link = elemento_siguiente.find("a", href=True)
            if link:
                href = link.get("href")
                if "soundcloud.com" in href:
                    audio_url = href
                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) > 5 and link_text != audio_url:
                        audio_titulo = link_text
                    break

        if not audio_url:
            return None

        resultado = "🎧 **Evangelio de hoy en audio**\n"
        if audio_titulo:
            resultado += f"**{audio_titulo}**\n"
        resultado += f'<a href="{audio_url}" target="_blank">Escuchar en SoundCloud</a>'
        return resultado

    def obtener_info_liturgica(fecha_obj):
        try:
            import psycopg2  # type: ignore
        except Exception:
            return None

        db_config = {
            "host": "db",
            "port": "5432",
            "user": "n8n_user",
            "password": "n8n_password",
            "database": "n8n",
        }

        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT dia, celebracion, color, tiempo_liturgico
                FROM calendario_liturgico
                WHERE fecha = %s
                """,
                (fecha_obj,),
            )
            resultado_db = cur.fetchone()
            cur.close()
            conn.close()

            if not resultado_db:
                return None

            dia, celebracion, color, tiempo_liturgico = resultado_db
            return {
                "dia": dia or "N/A",
                "celebracion": celebracion or "N/A",
                "color": color or "N/A",
                "tiempo_liturgico": tiempo_liturgico or "N/A",
            }
        except Exception:
            return None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        contenido_principal = soup.select_one("div.contenido-dia")
        source_url = url

        if not contenido_principal:
            url_fallback = f"https://www.dominicos.org/predicacion/homilia/{fecha.day:02d}-{fecha.month:02d}-{fecha.year}/lecturas/"
            response = requests.get(url_fallback, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            contenido_principal = soup
            source_url = url_fallback

        primera_lectura = extraer_seccion(contenido_principal, ["Primera lectura"])
        segunda_lectura = extraer_seccion(contenido_principal, ["Segunda lectura"])
        salmo = extraer_seccion(contenido_principal, ["Salmo de hoy", "Salmo"])
        evangelio = extraer_seccion(contenido_principal, ["Evangelio del día", "Evangelio"])
        reflexion = extraer_seccion(contenido_principal, ["Reflexión del Evangelio de hoy", "Reflexión"])
        video_youtube = extraer_video_youtube(contenido_principal)
        audio_soundcloud = extraer_audio_soundcloud(contenido_principal)

        resultado = f"{primera_lectura}\n\n"
        if segunda_lectura and "no encontrada" not in segunda_lectura:
            resultado += f"{segunda_lectura}\n\n"

        resultado += f"{salmo}\n\n{evangelio}\n\n"

        if reflexion and "no encontrada" not in reflexion:
            resultado += f"{reflexion}\n\n"

        if video_youtube:
            resultado += f"{video_youtube}\n\n"
        if audio_soundcloud:
            resultado += f"{audio_soundcloud}\n\n"

        resultado += "*(Fuente: dominicos.org)*"

        info_liturgica = obtener_info_liturgica(fecha)
        if info_liturgica:
            resultado += (
                "\n\n**Información Litúrgica**\n"
                f"Día: {info_liturgica['dia']}\n"
                f"Celebración: {info_liturgica['celebracion']}\n"
                f"Color: {info_liturgica['color']}\n"
                f"Tiempo Litúrgico: {info_liturgica['tiempo_liturgico']}"
            )

        lecturas = {
            "primera_lectura": primera_lectura,
            "segunda_lectura": segunda_lectura,
            "salmo": salmo,
            "evangelio": evangelio,
            "reflexion": reflexion,
            "video_youtube": video_youtube,
            "audio_soundcloud": audio_soundcloud,
            "info_liturgica": info_liturgica,
            "source_url": source_url,
        }

        return {
            "success": True,
            "message": f"Lecturas para {fecha.isoformat()} obtenidas exitosamente.",
            "data": lecturas,
            "result": resultado,
        }
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": f"Error al acceder a la página web: {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"Error al obtener lecturas: {exc}"}


def catolico_biblia_buscar(config, args: dict) -> dict:
    """
    Busca citas bíblicas o versículos por palabras clave.
    Migrado de n8n Herramienta Biblia.
    """
    modo = args.get("modo", "busqueda")
    libro = args.get("libro", "")
    capitulo = args.get("capitulo")
    versiculo_inicio = args.get("versiculo_inicio")
    versiculo_fin = args.get("versiculo_fin")
    texto = args.get("texto", "")

    return {
        "success": True,
        "message": "Búsqueda en la Biblia (Esqueleto).",
        "data": {
            "resultado": f"Resultados simulados para {modo} en libro '{libro}', texto '{texto}'."
        }
    }


def catolico_leer_documento(config, args: dict) -> dict:
    """
    Lee el contenido completo de un documento del RAG para que el agente pueda resumirlo.
    Recibe la URI o nombre del documento que devolvió la búsqueda RAG.
    """
    uri = args.get("uri", "")
    if not uri:
        return {"success": False, "error": "Debe proporcionar la URI del documento."}
    
    try:
        path = Path(uri)
        if not path.is_absolute():
            # Intentar resolver dentro de los stores si es relativo
            path = Path("/compose/documentos_listos/rag_teo") / uri
        
        if not path.exists():
             return {"success": False, "error": f"El documento no existe en la ruta {uri}"}
             
        contenido = path.read_text(encoding="utf-8")
        return {
            "success": True,
            "message": f"Documento {path.name} leído exitosamente. Procede a generar el resumen para el usuario.",
            "content": contenido
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
