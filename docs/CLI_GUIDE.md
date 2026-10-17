# 💻 Easy Convert CLI Guide

La CLI oficial de **Easy Convert** permite realizar conversiones de archivos privadas, rápidas y profesionales directamente desde cualquier terminal de tu sistema operativo.

---

## 🚀 Instalación y Disponibilidad Global

La CLI ya está configurada e instalada en tu entorno de usuario con `uv`.

### 1. Usar desde cualquier lugar de tu máquina:
El binario ejecutable `easy-convert` está disponible globalmente en tu terminal:

```bash
easy-convert --help
easy-convert --version
```

### 2. Si estás desarrollando dentro del repositorio:
```bash
uv run easy-convert --help
```

---

## 📋 Catálogo Completo de Comandos

La CLI se organiza en grupos lógicos según el tipo de archivo:

```
easy-convert
├── image      # Conversión, remoción de fondo con IA, compresión, watermark, to-pdf
├── doc        # Conversión de documentos (DOCX, PDF, ODT, HTML, Markdown, EPUB...)
├── pdf        # Operaciones PDF (merge, split, rotate, encrypt, decrypt)
├── audio      # Conversión de audio, bitrate, normalización de volumen, trim
├── video      # Conversión de video, CRF, resolución, framerate, extraer audio
├── xml        # Conversión XML a JSON, YAML, HTML (y XSLT)
├── base64     # Codificación de imagen a Base64 / Data URI y decodificación inversa
└── serve      # Levantar el servidor HTTP FastAPI con Uvicorn
```

---

## 📷 1. Imágenes (`easy-convert image`)

### Convertir Formato (`convert`)
Convierte entre más de 200 formatos (WebP, PNG, JPG, AVIF, HEIC, TIFF, BMP, GIF, SVG...):
```bash
# Conversión básica (guarda foto.webp al lado del archivo original)
easy-convert image convert foto.png -f webp

# Especificando archivo o carpeta de salida y calidad
easy-convert image convert foto.png -f webp -o ~/Descargas/foto_opt.webp -q 85

# Manteniendo metadatos EXIF (por defecto se eliminan para proteger privacidad)
easy-convert image convert foto.jpg -f png --no-strip-metadata
```

### Remover Fondo con IA (`remove-bg`)
Utiliza modelos neuronales (`rembg`) para eliminar fondos de imágenes:
```bash
# Quitar fondo por defecto (u2net) y guardar como PNG transparente
easy-convert image remove-bg retrato.jpg

# Usar un modelo específico (u2net, u2netp, u2net_human_seg, isnet-general-use, isnet-anime)
easy-convert image remove-bg persona.jpg -m u2net_human_seg -o sin_fondo.png

# Con alpha matting para bordes más suaves (pelo o detalles finos)
easy-convert image remove-bg modelo.png --alpha-matting
```

### Comprimir Imágenes (`compress`)
Comprime imágenes usando optimizadores especializados (lossless/lossy):
```bash
# Nivel de compresión: low (10-20%), balanced (30-60%), strong (60-90%)
easy-convert image compress foto.jpg --level strong

# Ajustar calidad numérica específica (1-100)
easy-convert image compress imagen.webp -q 75 -o salida.webp
```

### Añadir Marca de Agua (`watermark`)
Agrega una marca de agua de texto o un logotipo:
```bash
# Marca de agua de texto
easy-convert image watermark banner.png -t "CONFIDENCIAL" --position center --opacity 0.5

# Marca de agua con logotipo (posiciones: center, top-left, top-right, bottom-left, bottom-right)
easy-convert image watermark foto.jpg --logo logo.png --position bottom-right --opacity 0.8
```

### Imágenes a PDF (`to-pdf`)
Combina varias imágenes en un PDF multipágina conservando el orden:
```bash
easy-convert image to-pdf pagina1.png pagina2.jpg pagina3.png -o documento_completo.pdf
```

---

## 📄 2. Documentos (`easy-convert doc`)

Convierte entre formatos de texto y oficina utilizando **Pandoc** o **LibreOffice** de forma transparente:

```bash
# Convertir Markdown a PDF
easy-convert doc convert informe.md -f pdf

# Convertir Word a PDF
easy-convert doc convert contrato.docx -f pdf

# Convertir PDF a DOCX
easy-convert doc convert escaneo.pdf -f docx

# Convertir Markdown a HTML
easy-convert doc convert post.md -f html

# Forzar motor de conversión (--engine auto|pandoc|libreoffice)
easy-convert doc convert reporte.docx -f odt --engine libreoffice
```

---

## 📑 3. Operaciones con PDF (`easy-convert pdf`)

### Unir PDFs (`merge`)
Une dos o más archivos PDF en el orden en que se proporcionan:
```bash
easy-convert pdf merge portada.pdf capitulo1.pdf capitulo2.pdf -o libro_final.pdf
```

### Dividir / Extraer Páginas (`split`)
Extrae páginas específicas o rangos:
```bash
# Extraer páginas puntuales (ej. páginas 1, 3 y 5) a un nuevo PDF
easy-convert pdf split documento.pdf -p 1,3,5 -o seleccion.pdf

# Extraer un rango de páginas (genera un archivo ZIP con parte.pdf y resto.pdf)
easy-convert pdf split documento.pdf --start 2 --end 5 -o resultado.zip
```

### Rotar Páginas (`rotate`)
Gira páginas en ángulos múltiplos de 90° (90, 180, 270):
```bash
# Rotar todas las páginas 90 grados en sentido horario
easy-convert pdf rotate escaneo.pdf -r 90

# Rotar solo páginas específicas (ej. 1 y 4)
easy-convert pdf rotate plano.pdf -r 180 -p 1,4 -o plano_rotado.pdf
```

### Proteger con Contraseña (`encrypt`)
```bash
easy-convert pdf encrypt confidencial.pdf -p "MiClaveSegura123" -o protegido.pdf
```

### Desencriptar PDF (`decrypt`)
```bash
easy-convert pdf decrypt protegido.pdf -p "MiClaveSegura123" -o desbloqueado.pdf
```

---

## 🎵 4. Audio (`easy-convert audio`)

Convierte formatos de audio (MP3, WAV, FLAC, OGG, OPUS, AAC, M4A, etc.) y aplica procesamiento acústico con FFmpeg:

```bash
# Conversión simple
easy-convert audio convert cancion.wav -f mp3

# Conversión con bitrate específico (128k, 192k, 256k, 320k)
easy-convert audio convert track.flac -f mp3 -b 320k

# Normalización dinámica de volumen (estándar EBU R128 para podcasts/videos)
easy-convert audio convert podcast.wav -f mp3 --normalize

# Recortar audio (ej. iniciar en el segundo 30 y durar 60 segundos)
easy-convert audio convert audio.mp3 -f mp3 --trim-start 00:00:30 --trim-duration 60

# Ajustar canales a mono y sample rate a 44100 Hz
easy-convert audio convert voz.wav -f ogg --channels 1 --sample-rate 44100
```

---

## 🎬 5. Video (`easy-convert video`)

Conversión y manipulación de video (MP4, WebM, MKV, AVI, MOV, FLV, GIF...):

```bash
# Conversión básica de video
easy-convert video convert grabacion.mov -f mp4

# Control de calidad con CRF (0-51, menor = mayor calidad, 23 por defecto)
easy-convert video convert gameplay.mkv -f mp4 --crf 18

# Cambiar resolución y framerate
easy-convert video convert video.mp4 -f webp --resolution 1280:720 --fps 30

# Crear un GIF animado a partir de un fragmento de video
easy-convert video convert clip.mp4 -f gif --trim-start 00:00:05 --trim-duration 4

# Silenciar un video (quitar el audio por completo)
easy-convert video convert video_con_ruido.mp4 -f mp4 --mute

# Extraer solo la pista de audio a MP3 de alta calidad
easy-convert video extract-audio pelicula.mp4 -f mp3 -b 320k -o banda_sonora.mp3
```

---

## 🧬 6. XML (`easy-convert xml`)

Conversión de datos estructurados XML a otros formatos:

```bash
# Convertir XML a JSON
easy-convert xml to-json datos.xml -o datos.json

# Mantener atributos XML (con prefijo '@')
easy-convert xml to-json config.xml --preserve-attrs

# Convertir XML a YAML
easy-convert xml to-yaml datos.xml -o datos.yaml

# Transformar XML a HTML (usando tabla por defecto o XSLT personalizado)
easy-convert xml to-html reporte.xml -o reporte.html
easy-convert xml to-html reporte.xml --xslt plantilla.xslt -o estilizado.html
```

---

## 🔐 7. Base64 & Data URIs (`easy-convert base64`)

Ideal para copiar imágenes en el portapapeles, integraciones web o markdown:

```bash
# Codificar una imagen a Data URI (ej. data:image/png;base64,iVBORw...)
easy-convert base64 encode icono.png

# Codificar a Base64 puro (sin cabecera) y guardarlo en un archivo .txt
easy-convert base64 encode logo.png --raw -o logo_b64.txt

# Decodificar un Data URI o string Base64 directamente a archivo de imagen
easy-convert base64 decode "data:image/png;base64,iVBORw0KGgo..." -o imagen_restaurada.png

# Decodificar desde un archivo de texto con Base64
easy-convert base64 decode logo_b64.txt -o logo_restaurado.png
```

---

## 🌐 8. Servidor Web (`easy-convert serve`)

Comando para iniciar el backend HTTP de FastAPI:

```bash
# Levantar en 0.0.0.0:8000
easy-convert serve

# Personalizar puerto y habilitar auto-reload para desarrollo
easy-convert serve --port 8080 --reload

# En producción con múltiples workers
easy-convert serve --host 0.0.0.0 --port 8000 --workers 4
```
