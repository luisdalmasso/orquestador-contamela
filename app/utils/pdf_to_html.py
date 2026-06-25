import fitz  # PyMuPDF
import os
import logging

logger = logging.getLogger("conti.pdf_to_html")

def pdf_bytes_to_html(pdf_bytes: bytes, output_html_path: str, output_img_dir: str, relative_img_dir: str) -> None:
    """
    Convierte bytes de PDF a HTML con posicionamiento absoluto y extracción de imágenes.
    """
    # Asegurar que existan los directorios
    os.makedirs(output_img_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { background: #f0f0f0; margin: 0; padding: 20px; font-family: sans-serif; }
        .pagina { position: relative; margin: 20px auto; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); overflow: hidden; }
        .texto-bloque { position: absolute; font-family: sans-serif; white-space: nowrap; z-index: 2; }
        .img-bloque { position: absolute; z-index: 1; }
    </style>
</head>
<body>
"""

    img_contador = 0

    for num_pag in range(len(doc)):
        pagina = doc[num_pag]
        rect = pagina.rect
        ancho, alto = rect.width, rect.height

        html_content += f'<div class="pagina" style="width: {ancho}px; height: {alto}px;">'

        # Extraemos bloques (Texto tipo 0, Imágenes tipo 1)
        try:
            p_dict = pagina.get_text("dict")
        except Exception as e:
            logger.error(f"Error extrayendo texto en página {num_pag}: {e}")
            p_dict = {"blocks": []}

        for bloque in p_dict.get("blocks", []):
            if bloque["type"] == 0:
                for linea in bloque["lines"]:
                    x0, y0, x1, y1 = linea["bbox"]
                    for span in linea["spans"]:
                        texto = span["text"]
                        if 'Ã' in texto:
                            try:
                                texto = texto.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                            except Exception:
                                pass

                        tamano = span["size"]
                        color = span["color"]
                        r = (color >> 16) & 255
                        g = (color >> 8) & 255
                        b = color & 255
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"

                        html_content += f'<span class="texto-bloque" style="left: {x0}px; top: {y0}px; font-size: {tamano}px; color: {color_hex};">{texto}</span>'

            elif bloque["type"] == 1:
                x0, y0, x1, y1 = bloque["bbox"]
                ancho_img = x1 - x0
                alto_img = y1 - y0

                try:
                    irc = fitz.IRect(int(x0), int(y0), int(x1), int(y1))
                    pix = pagina.get_pixmap(clip=irc, matrix=fitz.Matrix(2, 2))

                    nombre_img = f"img_pag_{num_pag}_{img_contador}.png"
                    ruta_completa_img = os.path.join(output_img_dir, nombre_img)
                    pix.save(ruta_completa_img)
                    img_contador += 1

                    # Utilizar relative_img_dir para el src en el html
                    src_path = f"{relative_img_dir}/{nombre_img}".replace("//", "/")
                    html_content += f'<img class="img-bloque" src="{src_path}" style="left: {x0}px; top: {y0}px; width: {ancho_img}px; height: {alto_img}px;" />'
                except Exception as e:
                    logger.error(f"Error procesando bloque imagen en página {num_pag}: {e}")

        html_content += '</div>'

    html_content += "</body>\n</html>"

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
