# Fase 1 - Procesamiento Avanzado de Imágenes

## 🎯 Funcionalidades Implementadas

La **Fase 1** incluye conversión de formato y **3 operaciones avanzadas** de procesamiento de imagen a través de **endpoints individuales**:

### 1. **Eliminación de Fondo** 🎨
- Motor: **rembg** con modelos U2Net/BRIA
- Procesamiento 100% local (privacidad garantizada)
- Alpha matting opcional para bordes suaves
- Modelos disponibles: `u2net`, `u2netp`, `isnet-general-use`, `isnet-anime`, etc.
- Endpoint: `POST /api/v1/process/remove-background`

### 2. **Compresión Inteligente** 🗜️
- **3 niveles de compresión:**
  - `low`: 10-20% reducción (jpegoptim/oxipng lossless)
  - `balanced`: 30-60% reducción ⭐ **Recomendado** (mozjpeg/pngquant)
  - `strong`: 60-90% reducción (mozjpeg agresivo/pngquant fuerte)
- Detección automática de formato y herramienta óptima
- Endpoint: `POST /api/v1/process/compress`

### 3. **Marca de Agua** 💧
- **2 tipos:**
  - `text`: Texto personalizable con posición, opacidad, tamaño y color
  - `logo`: Logo PNG con auto-resize y control de opacidad
- **6 posiciones:** top-left, top-right, center, bottom-left, bottom-right, diagonal
- Endpoint: `POST /api/v1/process/watermark`

---

## 🔄 Pipeline de Procesamiento

El pipeline ejecuta operaciones en **orden optimizado** para máxima calidad:

```
Upload → Remove Background → Convert → Compress → Watermark → Output
```

**¿Por qué este orden?**
- Watermark después de comprimir previene degradación
- Remover fondo al inicio garantiza sujeto aislado
- Compresión actúa sobre el área final definitiva

**Nota:** Cada operación es un endpoint independiente que se puede invocar individualmente sobre archivos ya subidos.

---

## 📡 Endpoints API

### Flujo de Upload de Archivos

**Archivos <10MB:** Upload directo
```http
POST /api/v1/upload/{job_id}/file
```

**Archivos >10MB:** Chunked upload (manejado por frontend)
```http
POST /api/v1/upload/{job_id}/chunks/{chunk_number}
```

---

### 1. `POST /api/v1/process/remove-background`

Remueve el fondo de una imagen usando IA.

#### Request Body

```json
{
  "job_id": "abc123-def456",
  "output_format": "png",
  "model": "u2net",
  "alpha_matting": false,
  "strip_metadata": true
}
```

#### Response (202 Accepted)

```json
{
  "job_id": "abc123-def456",
  "status": "queued",
  "message": "Background removal queued successfully. Processing will start shortly.",
  "operation": "remove_background"
}
```

---

### 2. `POST /api/v1/process/compress`

Comprime una imagen con control de calidad.

#### Request Body

```json
{
  "job_id": "abc123-def456",
  "output_format": "webp",
  "level": "balanced",
  "quality": null,
  "strip_metadata": true
}
```

#### Parámetros

- `level`: `low` | `balanced` | `strong`
- `quality`: (opcional) Override manual 0-100
- `output_format`: `jpg` | `png` | `webp`

#### Response (202 Accepted)

```json
{
  "job_id": "abc123-def456",
  "status": "queued",
  "message": "Image compression (balanced) queued successfully.",
  "operation": "compress"
}
```

---

### 3. `POST /api/v1/process/watermark`

Añade marca de agua (texto o logo) a una imagen.

#### Request Body (Texto)

```json
{
  "job_id": "abc123-def456",
  "output_format": "jpg",
  "type": "text",
  "text": "© 2026 MyBrand",
  "position": "bottom-right",
  "opacity": 0.7,
  "font_size": 40,
  "color": "white",
  "margin": 20,
  "strip_metadata": true
}
```

#### Request Body (Logo)

```json
{
  "job_id": "abc123-def456",
  "output_format": "jpg",
  "type": "logo",
  "logo_path": "/path/to/logo.png",
  "position": "bottom-right",
  "opacity": 0.8,
  "size_percent": 15,
  "margin": 20,
  "strip_metadata": true
}
```

#### Response (202 Accepted)

```json
{
  "job_id": "abc123-def456",
  "status": "queued",
  "message": "Watermark (text) queued successfully.",
  "operation": "watermark"
}
```

---

## 🚀 Ejemplos de Uso

### Ejemplo 1: Remover fondo + Comprimir a WebP

```bash
# 1. Crear job
JOB_ID=$(curl -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{"input_format":"jpg","output_formats":["webp"],"original_size":1000000}' \
  | jq -r '.job_id')

# 2. Subir archivo
curl -X POST http://localhost:8000/api/v1/upload/$JOB_ID/file \
  -F "file=@product.jpg"

# 3. Remover fondo
curl -X POST http://localhost:8000/api/v1/process/remove-background \
  -H "Content-Type: application/json" \
  -d "{
    \"job_id\": \"$JOB_ID\",
    \"output_format\": \"png\",
    \"model\": \"u2net\",
    \"alpha_matting\": true
  }"

# 4. Comprimir
curl -X POST http://localhost:8000/api/v1/process/compress \
  -H "Content-Type: application/json" \
  -d "{
    \"job_id\": \"$JOB_ID\",
    \"output_format\": \"webp\",
    \"level\": \"balanced\"
  }"

# 5. Descargar
curl http://localhost:8000/api/v1/jobs/$JOB_ID/download -o product-processed.webp
```

**Caso de uso:** Crear thumbnails de productos para e-commerce con fondo transparente y peso optimizado.

---

### Ejemplo 2: Solo comprimir imagen

```bash
# Imagen ya subida con job_id
curl -X POST http://localhost:8000/api/v1/process/compress \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "def456",
    "output_format": "jpg",
    "level": "strong",
    "quality": 80,
    "strip_metadata": true
  }'
```

**Caso de uso:** Reducir peso de imágenes para web sin perder calidad perceptual.

---

### Ejemplo 3: Solo marca de agua

```bash
curl -X POST http://localhost:8000/api/v1/process/watermark \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "ghi789",
    "output_format": "jpg",
    "type": "text",
    "text": "© My Portfolio",
    "position": "bottom-right",
    "opacity": 0.6,
    "font_size": 32,
    "color": "white"
  }'
```

**Caso de uso:** Añadir marca de agua a imágenes de portafolio.
---

### Ejemplo 4: Pipeline completo (múltiples operaciones)

```bash
# 1. Crear job y subir archivo
JOB_ID=$(curl -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{"input_format":"jpg","output_formats":["webp"],"original_size":2000000}' \
  | jq -r '.job_id')

curl -X POST http://localhost:8000/api/v1/upload/$JOB_ID/file \
  -F "file=@portfolio.jpg"

# 2. Remover fondo
curl -X POST http://localhost:8000/api/v1/process/remove-background \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\",\"output_format\":\"png\",\"model\":\"u2net\"}"

# 3. Comprimir
curl -X POST http://localhost:8000/api/v1/process/compress \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\",\"output_format\":\"webp\",\"level\":\"balanced\"}"

# 4. Añadir watermark
curl -X POST http://localhost:8000/api/v1/process/watermark \
  -H "Content-Type: application/json" \
  -d "{
    \"job_id\":\"$JOB_ID\",
    \"output_format\":\"webp\",
    \"type\":\"text\",
    \"text\":\"© 2026 Brand\",
    \"position\":\"bottom-right\",
    \"opacity\":0.5
  }"
```

**Caso de uso:** Pipeline completo para imágenes de portafolio profesional.

---

## 🛠️ Herramientas Instaladas

### Contenedores (Podman/Docker)

```dockerfile
# Procesamiento de imagen
- ImageMagick 7+        # Conversión, watermark
- rembg[gpu]           # Eliminación de fondo con IA

# Compresión JPEG
- mozjpeg (cjpeg)      # Compresión balanced/strong
- jpegoptim            # Compresión light

# Compresión PNG
- oxipng               # Lossless (balanced)
- pngquant             # Lossy (strong)
```

Instalados en: `/opt/mozjpeg/bin/cjpeg` y `/usr/local/bin/oxipng`

---

## 📊 Comparativa de Compresión

| Nivel | JPEG | PNG | Reducción | Calidad Visual |
|-------|------|-----|-----------|----------------|
| **Low** | jpegoptim max=90 | oxipng -o4 | 10-20% | Idéntica |
| **Balanced** ⭐ | mozjpeg q=75 | pngquant 65-85 | 30-60% | Imperceptible |
| **Strong** | mozjpeg q=60 | pngquant 40-65 | 60-90% | Aceptable |

---

## 🔒 Privacidad

Todas las operaciones mantienen el modelo **privacy-first**:

- ✅ Procesamiento 100% local (sin APIs externas)
- ✅ Metadata EXIF eliminada por defecto (`strip_metadata: true`)
- ✅ Archivos temporales auto-limpiados
- ✅ rembg no envía datos a la nube
- ✅ Sin logs de contenido de archivo

---

## 📝 Notas Técnicas

### Arquitectura de Endpoints

Cada operación es un **endpoint independiente** que trabaja sobre archivos ya subidos:

- **Ventajas:**
  - Mayor flexibilidad (aplicar solo operaciones necesarias)
  - Mejor control de flujo desde el cliente
  - Menor complejidad en requests
  - Más fácil de testear y debuggear

- **Workflow típico:**
  1. `POST /upload/create` → obtener job_id
  2. `POST /upload/{job_id}/file` → subir archivo
  3. Aplicar operaciones individuales en el orden deseado
  4. `GET /jobs/{job_id}/download` → descargar resultado

### Orden de Operaciones Recomendado

El pipeline interno respeta el orden óptimo:

1. **Background removal** primero para trabajar con sujeto aislado
2. **Convert** al formato objetivo
3. **Compress** para reducir peso manteniendo calidad
4. **Watermark** al final para evitar degradación

### Eventos de Dominio

Cada operación genera un evento para auditoría:
- `ImageProcessingConfigured`
- `BackgroundRemoved`
- `ImageCompressed`
- `WatermarkApplied`

Estos eventos se persisten con Event Sourcing para trazabilidad completa.

---

## 🧪 Testing

Ver documentación de tests en [TESTING.md](./TESTING.md) para:
- 45 unit tests (services individuales)
- 13 integration tests (pipeline completo)
- Coverage >85%

Carpeta de imágenes de test: `/images/` (samples para desarrollo)

---

## 🎉 Listo para Producción

El código implementado incluye:

- ✅ Event Sourcing completo
- ✅ Manejo de errores robusto
- ✅ Logging estructurado
- ✅ Retry automático (BullMQ)
- ✅ Documentación OpenAPI
- ✅ Type hints completos
- ✅ Sin errores de linting
- ✅ 3 endpoints individuales (remove-background, compress, watermark)
- ✅ Upload flow documentado (<10MB vs >10MB)

**Fase 1 completada** ✨
