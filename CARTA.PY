import fitz  # PyMuPDF
import os

def pdf_a_html_con_imagenes(ruta_pdf, ruta_html, carpeta_img="img_carta"):
    # Crear la carpeta para guardar las imágenes si no existe
    if not os.path.exists(carpeta_img):
        os.makedirs(carpeta_img)
        
    doc = fitz.open(ruta_pdf)
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            .pagina { position: relative; margin: 20px auto; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); overflow: hidden; }
            .texto-bloque { position: absolute; font-family: sans-serif; white-space: nowrap; z-index: 2; }
            .img-bloque { position: absolute; z-index: 1; }
        </style>
    </head>
    <body style="background: #f0f0f0; margin: 0; padding: 20px;">
    """

    img_contador = 0

    for num_pag in range(len(doc)):
        pagina = doc[num_pag]
        rect = pagina.rect
        ancho, alto = rect.width, rect.height
        
        html_content += f'<div class="pagina" style="width: {ancho}px; height: {alto}px;">'
        
        # Extraemos TODOS los bloques (Texto tipo 0, Imágenes tipo 1)
        p_dict = pagina.get_text("dict")
        
        for bloque in p_dict["blocks"]:
            # --- PROCESAR TEXTO (Tipo 0) ---
            if bloque["type"] == 0:
                for linea in bloque["lines"]:
                    x0, y0, x1, y1 = linea["bbox"]
                    for span in linea["spans"]:
                        texto = span["text"]
                        # Corregir encoding si vienen caracteres rotos
                        if 'Ã' in texto:
                            texto = texto.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                        
                        tamano = span["size"]
                        color = span["color"]
                        r = (color >> 16) & 255
                        g = (color >> 8) & 255
                        b = color & 255
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"
                        
                        html_content += f'<span class="texto-bloque" style="left: {x0}px; top: {y0}px; font-size: {tamano}px; color: {color_hex};">{texto}</span>'
            
            # --- PROCESAR IMÁGENES (Tipo 1) ---
            elif bloque["type"] == 1:
                x0, y0, x1, y1 = bloque["bbox"]
                ancho_img = x1 - x0
                alto_img = y1 - y0
                
                # Obtener los metadatos de la imagen dentro del PDF
                imagen_list = pagina.get_images(full=True)
                
                # Si la página contiene imágenes renderizables
                if imagen_list:
                    # Buscamos la imagen correspondiente a este bloque (por índice o proximidad)
                    # Para simplificar y asegurar calidad, hacemos un pixmap (render) del área del bloque:
                    irc = fitz.IRect(int(x0), int(y0), int(x1), int(y1))
                    pix = pagina.get_pixmap(clip=irc, matrix=fitz.Matrix(2, 2)) # Matrix(2,2) mejora la calidad/resolución
                    
                    # Guardar la imagen en disco
                    nombre_img = f"img_pag_{num_pag}_{img_contador}.png"
                    ruta_completa_img = os.path.join(carpeta_img, nombre_img)
                    pix.save(ruta_completa_img)
                    img_contador += 1
                    
                    # Insertar la imagen en el HTML con su posición y tamaño exactos
                    html_content += f'<img class="img-bloque" src="{carpeta_img}/{nombre_img}" style="left: {x0}px; top: {y0}px; width: {ancho_img}px; height: {alto_img}px;" />'

        html_content += '</div>'
        
    html_content += "</body></html>"
    
    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Éxito: HTML generado en '{ruta_html}' con las imágenes guardadas en '{carpeta_img}/'")

# Ejecutar el script
pdf_a_html_con_imagenes("Carta.pdf", "Carta_Con_Imagenes.html")