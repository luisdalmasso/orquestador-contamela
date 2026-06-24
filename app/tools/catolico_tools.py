from pathlib import Path
import requests
from bs4 import BeautifulSoup
import datetime
import re

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

    def extraer_video_youtube(full_soup):
        html_str = str(full_soup)
        
        # Buscar ID de video de YouTube mediante regex en todo el HTML (iframes, scripts, data-src)
        yt_match = re.search(r'(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})', html_str)
        if yt_match:
            video_id = yt_match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return f"🎥 **Evangelio de hoy en vídeo**\n<a href=\"{video_url}\" target=\"_blank\">Ver en YouTube</a>"
            
        # Búsqueda de iframe ofuscado por plugins de cookies
        iframe = full_soup.find("iframe", attrs={"data-src": lambda s: s and ("youtube" in s.lower() or "youtu.be" in s.lower())})
        if iframe:
            return f"🎥 **Evangelio de hoy en vídeo**\n<a href=\"{iframe.get('data-src')}\" target=\"_blank\">Ver en YouTube</a>"
            
        return None

    def extraer_audio_soundcloud(full_soup):
        html_str = str(full_soup)
        
        # Buscar reproductor embebido de soundcloud
        sc_match = re.search(r'(https://w\.soundcloud\.com/player/\?url=[^"\'\s&]+)', html_str)
        if sc_match:
            audio_url = sc_match.group(1)
            return f"🎧 **Evangelio de hoy en audio**\n<a href=\"{audio_url}\" target=\"_blank\">Escuchar en SoundCloud</a>"
            
        # Buscar enlace directo a un track
        sc_link_match = re.search(r'(https://soundcloud\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)', html_str)
        if sc_link_match:
            audio_url = sc_link_match.group(1)
            return f"🎧 **Evangelio de hoy en audio**\n<a href=\"{audio_url}\" target=\"_blank\">Escuchar en SoundCloud</a>"
            
        return None

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
        video_youtube = extraer_video_youtube(soup)
        audio_soundcloud = extraer_audio_soundcloud(soup)

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


def catolico_listar_titulos(config, args: dict) -> dict:
    """
    Lista todos los títulos y nombres de archivo de documentos ingestados
    en el store católico. Lee el front-matter YAML de cada .md en
    /compose/documentos_listos/{store}/ y devuelve {titulo, filename}.

    Útil para validar si un documento existe antes de intentar resumirlo,
    y para encontrar el título más similar a lo que pidió el usuario.
    """
    import re as _re

    store = args.get("store", "catolico")
    docs_dir = Path("/compose/documentos_listos") / store

    if not docs_dir.exists():
        return {
            "success": False,
            "error": f"El directorio del store '{store}' no existe.",
            "documentos": [],
            "total": 0,
        }

    documentos = []
    for md_file in sorted(docs_dir.glob("*.md")):
        try:
            header = md_file.read_text(encoding="utf-8")[:600]
        except Exception:
            continue

        titulo = ""
        if header.startswith("---"):
            # Extraer campo title del front-matter YAML
            m = _re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', header, _re.MULTILINE)
            if m:
                titulo = m.group(1).strip()

        # Si no hay título en front-matter, derivar del nombre de archivo
        if not titulo:
            titulo = md_file.stem.replace("-", " ").replace("_", " ").title()

        documentos.append({
            "titulo": titulo,
            "filename": md_file.name,
        })

    return {
        "success": True,
        "store": store,
        "total": len(documentos),
        "documentos": documentos,
    }


def catolico_leer_documento(config, args: dict) -> dict:
    """
    Lee el contenido completo de un documento del RAG para que el agente pueda resumirlo.

    Modos de uso:
      1. Por URI exacta (la que devuelve search_rag): args = {"uri": "local://catolico/..."}
      2. Por query de búsqueda (más flexible): args = {"query": "...", "store": "catolico"}
         → busca en flamehaven, toma el doc #1 y devuelve su contenido completo.
         → útil cuando search_rag devolvió resultados dudosos o múltiples.
    """
    import urllib.parse

    uri = args.get("uri", "").strip()
    query = args.get("query", "").strip()
    store = args.get("store", "catolico")

    # ── Modo 2: por query ───────────────────────────────────────────────────────
    if query and not uri:
        # Primero: búsqueda local por title en front-matter YAML (más precisa y sin RAG)
        import re as _re
        docs_dir = Path("/compose/documentos_listos") / store
        query_lower = query.lower()
        best_path = None
        best_score = -1
        if docs_dir.exists():
            for md_file in docs_dir.glob("*.md"):
                try:
                    header = md_file.read_text(encoding="utf-8")[:500]
                    m = _re.search(r'title:\s*(.+?)\s*$', header, _re.MULTILINE)
                    if m:
                        title_val = m.group(1).strip().strip('"').strip("'").lower()
                        # Calcular score: palabras del query que aparecen en el título
                        words = [w for w in _re.split(r'\W+', query_lower) if len(w) > 2]
                        score = sum(1 for w in words if w in title_val)
                        # Bonus: el título empieza con la query (coincidencia exacta al inicio)
                        if title_val.startswith(query_lower):
                            score += 10
                        if score > best_score:
                            best_score = score
                            best_path = md_file
                except Exception:
                    pass
        if best_path and best_score > 0:
            uri = str(best_path)
        else:
            # Fallback: búsqueda en flamehaven RAG
            try:
                from app.tools.rag_search_tools import _flamehaven_post, _get_rag_creds, _clean_sources
                api_key, base_url = _get_rag_creds(config)
                result = _flamehaven_post("/api/search", {
                    "query": query,
                    "store_name": store,
                    "search_mode": "hybrid",
                    "max_tokens": 1,
                }, api_key, base_url)
                sources = _clean_sources(result.get("sources", []))
                if not sources:
                    return {"success": False, "error": f"No se encontraron documentos para: {query}"}
                # Tomar la URI del mejor resultado
                uri = sources[0].get("uri", "")
                if not uri:
                    return {"success": False, "error": "El resultado de búsqueda no tiene URI."}
            except Exception as e:
                return {"success": False, "error": f"Error buscando en RAG: {e}"}


    if not uri:
        return {"success": False, "error": "Debe proporcionar 'uri' o 'query'."}

    # ── Resolver URI → path real ───────────────────────────────────────────────
    # La URI tiene forma: local://catolico/%2Fcompose%2F...%2Farchivo.md
    # o bien puede venir ya como path: /compose/documentos_listos/...
    resolved_path = None

    if uri.startswith("local://"):
        # Extraer la parte después del store name
        # local://catolico/<encoded_path>
        rest = uri.split("local://", 1)[1]
        # rest = "catolico/%2Fcompose%2F..."
        slash_idx = rest.find("/")
        if slash_idx != -1:
            encoded_path = rest[slash_idx + 1:]
            decoded = urllib.parse.unquote(encoded_path)
            resolved_path = Path(decoded)
    else:
        # Asumir que es un path directo o nombre de archivo
        path = Path(uri)
        if path.is_absolute():
            resolved_path = path
        else:
            resolved_path = Path("/compose/documentos_listos/catolico") / uri

    if resolved_path is None or not resolved_path.exists():
        # Último intento: buscar por nombre de archivo en documentos_listos
        if resolved_path:
            fname = resolved_path.name
            candidates = list(Path("/compose/documentos_listos/catolico").glob(fname))
            if candidates:
                resolved_path = candidates[0]
            else:
                return {
                    "success": False,
                    "error": f"Documento no encontrado: {resolved_path}",
                    "hint": "Buscá el documento en https://contamela.com/docs_chatui o usá search_rag para obtener una URI válida."
                }
        else:
            return {"success": False, "error": f"No se pudo resolver la URI: {uri}"}

    try:
        contenido = resolved_path.read_text(encoding="utf-8")
        # Quitar YAML front-matter si existe para devolver contenido limpio
        if contenido.startswith("---\n"):
            end = contenido.find("\n---\n", 4)
            if end != -1:
                contenido = contenido[end + 5:]
        # Construir URL pública: /compose/documentos_listos/catolico/archivo.md → https://contamela.com/docs_chatui/catolico/archivo.md
        rel = None
        try:
            rel = resolved_path.relative_to("/compose/documentos_listos")
        except ValueError:
            pass
        public_url = f"https://contamela.com/docs_chatui/{rel}" if rel else None
        return {
            "success": True,
            "filename": resolved_path.name,
            "path": str(resolved_path),
            "public_url": public_url,
            "size_chars": len(contenido),
            "content": contenido,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def catolico_resumir_documento(config, args: dict) -> dict:
    """
    Genera un resumen estructurado de un documento católico usando SpineDigest.
    Pipeline: chunking → grafo de conocimiento → defensa multi-agente.
    Cachea el resultado .sdpub para evitar re-procesar el mismo documento.
    """
    import subprocess
    import hashlib
    import os
    import urllib.parse

    query = args.get("query", "").strip()
    store = args.get("store", "catolico").strip()
    prompt = args.get("prompt", (
        "Extrae las enseñanzas doctrinales principales, citas bíblicas y "
        "magisteriales, argumentos teológicos centrales y conclusiones pastorales. "
        "Mantén el orden lógico del documento original."
    ))

    if not query:
        return {"success": False, "error": "Parámetro 'query' requerido."}

    # ── 1. Resolver el archivo .md usando la búsqueda local por front-matter ──
    base_dir = Path(f"/compose/documentos_listos/{store}")
    if not base_dir.exists():
        return {"success": False, "error": f"Store no encontrado: {store}"}

    query_words = [w for w in query.lower().split() if len(w) > 2]
    best_score = 0
    best_path = None

    for md_file in base_dir.glob("*.md"):
        try:
            header = md_file.read_text(encoding="utf-8")[:500]
        except Exception:
            continue
        title_line = ""
        for line in header.splitlines():
            if line.lower().startswith("title:"):
                title_line = line.split(":", 1)[1].strip().strip('"').lower()
                break
        if not title_line:
            continue
        score = sum(1 for w in query_words if w in title_line)
        if title_line.startswith(query.lower()):
            score += 10
        if score > best_score:
            best_score = score
            best_path = md_file

    if not best_path or best_score == 0:
        return {
            "success": False,
            "error": f"No se encontró un documento con título similar a: {query}",
        }

    # ── 2. Determinar ruta de caché ──
    cache_dir = Path("/compose/documentos_listos/.spinedigest_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Hash basado en contenido del archivo + prompt para invalidar si cambia
    try:
        content_hash = hashlib.md5(best_path.read_bytes()).hexdigest()[:12]
    except Exception:
        content_hash = best_path.stem[:12]

    sdpub_path = cache_dir / f"{best_path.stem}-{content_hash}.sdpub"
    md_out_path = cache_dir / f"{best_path.stem}-{content_hash}.md"

    titulo = best_path.stem.replace("-", " ").title()
    # Intentar extraer título del front-matter
    try:
        header = best_path.read_text(encoding="utf-8")[:500]
        for line in header.splitlines():
            if line.lower().startswith("title:"):
                titulo = line.split(":", 1)[1].strip().strip('"')
                break
    except Exception:
        pass

    # ── 3. Si ya existe el resumen en caché, devolver directamente ──
    if md_out_path.exists():
        try:
            summary = md_out_path.read_text(encoding="utf-8").strip()
            _rel = None
            try:
                _rel = best_path.relative_to("/compose/documentos_listos")
            except ValueError:
                pass
            return {
                "success": True,
                "titulo": titulo,
                "content": summary,
                "source_file": str(best_path),
                "public_url": f"https://contamela.com/docs_chatui/{_rel}" if _rel else None,
                "cached": True,
            }
        except Exception:
            pass  # Si falla la lectura, regenerar

    # ── 4. Ejecutar spinedigest ──
    env = os.environ.copy()
    # Credenciales LLM (Gemini)
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        env["SPINEDIGEST_LLM_PROVIDER"] = "google"
        env["SPINEDIGEST_LLM_MODEL"] = "gemini-2.0-flash"
        env["SPINEDIGEST_LLM_API_KEY"] = gemini_key
    # Asegurar que el prompt viaja como var de entorno (evita escaping en CLI)
    env["SPINEDIGEST_PROMPT"] = prompt

    cmd = [
        "spinedigest",
        "--input", str(best_path),
        "--output", str(md_out_path),
        "--output-format", "markdown",
    ]

    # Si ya existe el .sdpub, usarlo para re-exportar sin re-llamar LLM
    if sdpub_path.exists():
        cmd = [
            "spinedigest",
            "--input", str(sdpub_path),
            "--output", str(md_out_path),
            "--output-format", "markdown",
        ]
    else:
        # Primera vez: también guardar el .sdpub para futuras re-exportaciones
        cmd = [
            "spinedigest",
            "--input", str(best_path),
            "--output", str(sdpub_path),
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1200, env=env
        )
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"SpineDigest falló: {result.stderr[:500]}",
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SpineDigest tardó demasiado (>20 min)."}
    except FileNotFoundError:
        return {"success": False, "error": "spinedigest no está instalado en el PATH."}

    # Si generamos el .sdpub, ahora exportar a Markdown
    if not md_out_path.exists() and sdpub_path.exists():
        export_cmd = [
            "spinedigest",
            "--input", str(sdpub_path),
            "--output", str(md_out_path),
            "--output-format", "markdown",
        ]
        try:
            result2 = subprocess.run(
                export_cmd, capture_output=True, text=True, timeout=60, env=env
            )
            if result2.returncode != 0:
                return {
                    "success": False,
                    "error": f"SpineDigest export falló: {result2.stderr[:500]}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    if not md_out_path.exists():
        return {"success": False, "error": "SpineDigest no generó el archivo de salida."}

    try:
        summary = md_out_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        return {"success": False, "error": f"Error leyendo resumen: {e}"}

    _rel = None
    try:
        _rel = best_path.relative_to("/compose/documentos_listos")
    except ValueError:
        pass
    return {
        "success": True,
        "titulo": titulo,
        "content": summary,
        "source_file": str(best_path),
        "public_url": f"https://contamela.com/docs_chatui/{_rel}" if _rel else None,
        "cached": False,
    }
