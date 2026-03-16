# Fase 2 - Conversión de Documentos

## 🎯 Funcionalidades Implementadas

La **Fase 2** agrega conversión de documentos con selección automática de motor y **validación de seguridad por tipo MIME**:

### 1. **Conversión de Documentos** 📄
- **Motor Pandoc** – documentos de texto y markup (md, html, rst, epub, docx, pdf, etc.)
- **Motor LibreOffice headless** – documentos Office de alta fidelidad (doc, xls, ppt, etc.)
- Selección automática del motor según formato de entrada/salida
- Override explícito disponible (`auto`, `pandoc`, `libreoffice`)
- Endpoint: `POST /api/v1/process/document`

### 2. **Validación de Tipo MIME** 🔒
- Verificación con `libmagic` (python-magic) antes de encolar cualquier job
- Detecta archivos maliciosos que declaran un formato incorrecto
- Comportamiento inteligente: permisivo con formatos de texto ambiguos (`md`, `rst`, `csv`, `tex`), estricto con formatos binarios
- Aplicado en los tres handlers de procesamiento: imágenes, pipeline de imágenes y documentos

### 3. **Timeout Específico para Documentos** ⏱️
- Conversiones de documentos usan un timeout dedicado: `MAX_DOCUMENT_CONVERSION_TIME_SECONDS`
- Valor por defecto: **900s (15 minutos)**
- El timeout general (`MAX_CONVERSION_TIME_SECONDS`) sigue aplicando al resto de conversiones

### 4. **Soporte Actual de PDF como Entrada** 📌
- `pdf -> txt` se procesa con extracción de texto (`pypdf`).
- `pdf -> docx` se procesa con `pdf2docx`.
- `pdf -> odt` se procesa como pipeline `pdf2docx` -> `docx -> odt` (LibreOffice).
- Para PDFs escaneados, la calidad depende de OCR previo.

### 5. **Procesador PDF Dedicado (Manipulación y Edición)** 🧩
Se incorporó una capa específica de procesamiento PDF, separada de la conversión documental clásica, con dos motores:

- **pypdf** para operaciones estructurales:
  - unir PDFs
  - extraer páginas
  - eliminar páginas
  - rotar páginas
  - actualizar metadatos
  - cifrar / descifrar

- **PyMuPDF (fitz)** para edición visual:
  - insertar texto
  - insertar imagen
  - dibujar rectángulos
  - añadir anotaciones
  - ajustar mediabox/layout

Endpoints disponibles en:

- `POST /api/v1/process/pdf/merge`
- `POST /api/v1/process/pdf/extract-pages`
- `POST /api/v1/process/pdf/delete-pages`
- `POST /api/v1/process/pdf/rotate`
- `POST /api/v1/process/pdf/metadata`
- `POST /api/v1/process/pdf/encrypt`
- `POST /api/v1/process/pdf/decrypt`
- `POST /api/v1/process/pdf/add-text`
- `POST /api/v1/process/pdf/add-image`
- `POST /api/v1/process/pdf/draw-rectangle`
- `POST /api/v1/process/pdf/add-annotation`
- `POST /api/v1/process/pdf/set-mediabox`

Implementación interna:

- `ProcessPdfCommand` y `ProcessPdfHandler` construyen `pdf_config` y lo encolan.
- `ConversionWorker` enruta jobs con `pdf_config` hacia `PdfProcessor`.
- Las salidas se descargan con el mismo flujo estándar de jobs (`GET /jobs/{job_id}/download`).

---

## 🔀 Selección de Motor

Modo `auto` está optimizado para rendimiento:
- Entradas Office-like (`docx`, `odt`, `xlsx`, `pptx`, etc.) priorizan **LibreOffice**.
- Entradas markup/texto (`md`, `html`, `rst`, `tex`) priorizan **Pandoc**.
- Salidas textuales (`md`, `html`, `txt`, `rst`, `latex`, `epub`) priorizan **Pandoc** aunque la entrada sea Office.
- Si necesitas lo contrario, usa `preferred_engine` explícito.

| Formato Entrada | Motor Preferido | Razón |
|---|---|---|
| `md`, `html`, `rst`, `epub`, `txt` | Pandoc | Markup nativo |
| `latex`, `tex` | Pandoc | TeX nativo |
| `doc`, `xls`, `ppt`, `pptx` | LibreOffice | Formato Office propietario |
| `xlsx`, `ods`, `odp`, `odg` | LibreOffice | OpenDocument/OOXML |
| `docx`, `odt` → `md/html/txt/rst/latex/epub` | Pandoc | Conversión semántica más rápida y estable |
| `docx`, `odt` → `pdf/docx/odt` | LibreOffice | Mejor performance para salida Office/PDF en modo auto |
| pdf (salida) desde Office | LibreOffice | Menor latencia de conversión en modo auto |

---

## 🔄 Flujo Completo

```
POST /upload/create  →  POST /upload/{job_id}/file  →  POST /process/document  →  GET /jobs/{job_id}  →  GET /jobs/{job_id}/download
```

---

## 📡 Endpoints API

### `POST /api/v1/process/document`

Encola la conversión de un documento ya subido.

#### Request Body

```json
{
  "job_id": "abc123-def456",
  "output_format": "pdf",
  "preferred_engine": "auto"
}
```

### Variables de entorno relacionadas

```bash
# Timeout general (imágenes y otros procesos)
MAX_CONVERSION_TIME_SECONDS=300

# Timeout dedicado para documentos (Pandoc/LibreOffice)
MAX_DOCUMENT_CONVERSION_TIME_SECONDS=900
```

#### Parámetros

| Campo | Tipo | Descripción |
|---|---|---|
| `job_id` | `string` | ID del job obtenido en `/upload/create` |
| `output_format` | `string` | Formato destino: `pdf`, `docx`, `html`, `epub`, `odt`, `txt`, etc. |
| `preferred_engine` | `string` | `auto` (recomendado), `pandoc`, `libreoffice` |

#### Response (202 Accepted)

```json
{
  "job_id": "abc123-def456",
  "status": "queued",
  "message": "Document conversion queued successfully.",
  "document_config": {
    "output_format": "pdf",
    "preferred_engine": "auto"
  }
}
```

---

## 🔒 Validación de Tipo MIME

La validación ocurre automáticamente antes de encolar cualquier job de procesamiento.

### Comportamiento

| Escenario | Resultado |
|---|---|
| JPEG declarado como `jpg` | ✅ Permitido |
| PNG subido declarado como `jpg` | ❌ `400 Bad Request` |
| PDF subido declarado como `docx` | ❌ `400 Bad Request` |
| Texto plano declarado como `docx` | ❌ `400 Bad Request` |
| Texto plano declarado como `md`, `rst`, `csv` | ✅ Permitido (text/plain es ambiguo) |
| MIME desconocido | ✅ Permitido con warning en logs |
| `libmagic` no disponible | ✅ Permitido (falla abierta, no cierra el servicio) |

### Error de Validación (400)

```json
{
  "detail": "File content does not match declared format. Declared: 'jpg', detected: 'image/png'."
}
```

---

## 🚀 Ejemplos de Uso

### Ejemplo 1: Markdown → PDF

```bash
# 1. Crear job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{"input_format":"md","output_formats":["pdf"],"original_size":5000}' \
  | jq -r '.job_id')

# 2. Subir archivo
curl -X POST http://localhost:8000/api/v1/upload/$JOB_ID/file \
  -F "file=@document.md"

# 3. Iniciar conversión
curl -X POST http://localhost:8000/api/v1/process/document \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\",\"output_format\":\"pdf\",\"preferred_engine\":\"auto\"}"

# 4. Verificar estado
curl http://localhost:8000/api/v1/jobs/$JOB_ID

# 5. Descargar resultado
curl -o resultado.pdf http://localhost:8000/api/v1/jobs/$JOB_ID/download
```

### Ejemplo 2: DOCX → HTML (LibreOffice forzado)

```bash
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{"input_format":"docx","output_formats":["html"],"original_size":250000}' \
  | jq -r '.job_id')

curl -X POST http://localhost:8000/api/v1/upload/$JOB_ID/file \
  -F "file=@report.docx"

curl -X POST http://localhost:8000/api/v1/process/document \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\",\"output_format\":\"html\",\"preferred_engine\":\"libreoffice\"}"
```

### Ejemplo 3: Excel → CSV

```bash
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{"input_format":"xlsx","output_formats":["csv"],"original_size":80000}' \
  | jq -r '.job_id')

curl -X POST http://localhost:8000/api/v1/upload/$JOB_ID/file \
  -F "file=@data.xlsx"

curl -X POST http://localhost:8000/api/v1/process/document \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\",\"output_format\":\"csv\",\"preferred_engine\":\"auto\"}"
```

---

## 📦 Formatos Soportados

### Entrada

| Categoría | Formatos |
|---|---|
| Markup / Texto | `md`, `markdown`, `html`, `htm`, `rst`, `txt`, `latex`, `tex` |
| Documentos Office | `doc`, `docx`, `odt`, `rtf` |
| Hojas de Cálculo | `xls`, `xlsx`, `ods`, `csv`, `tsv` |
| Presentaciones | `ppt`, `pptx`, `odp` |
| eBook / Otros | `epub`, `pdf` (salidas soportadas: `txt`, `docx`, `odt`) |

### Salida

| Categoría | Formatos |
|---|---|
| Markup / Texto | `md`, `markdown`, `html`, `txt`, `latex`, `tex`, `rst` |
| Documentos Office | `docx`, `odt`, `rtf` |
| Hojas de Cálculo | `xlsx`, `ods`, `csv`, `tsv` |
| Presentaciones | `pptx`, `odp` |
| eBook / PDF | `epub`, `pdf` |

---

## 🏗️ Arquitectura Interna

### Archivos Nuevos / Modificados

| Archivo | Cambio |
|---|---|
| `src/infrastructure/converters/document_converter.py` | **NUEVO** — Motor de conversión con Pandoc/LibreOffice |
| `src/infrastructure/mime_validator.py` | **NUEVO** — Validación de tipo MIME con libmagic |
| `src/interfaces/http/controllers/document_processing_controller.py` | **NUEVO** — Endpoint `POST /process/document` |
| `src/application/commands.py` | `ProcessDocumentCommand` agregado |
| `src/application/handlers.py` | `ProcessDocumentHandler` + MIME validation en los 3 handlers |
| `src/infrastructure/worker/conversion_worker.py` | Routing imagen vs documento |
| `src/interfaces/http/controllers/job_controller.py` | MIME types de descarga para formatos de documento |
| `shared/config/settings.py` | Listas de formatos de documentos + `is_document_format_supported()` |
| `Containerfile` / `Dockerfile` | `libreoffice`, `pandoc`, `texlive`, `libmagic1` |

### Seguridad LibreOffice

Para evitar colisiones de perfiles cuando múltiples jobs se procesan en paralelo:

```python
lo_home = out_dir / f"lo_home_{job_id}"  # directorio HOME aislado por job
env = {**os.environ, "HOME": str(lo_home)}
subprocess.run(["libreoffice", "--headless", ...], env=env)
```

---

## 🧪 Tests

```bash
# Unit tests del conversor de documentos
uv run pytest tests/unit/test_document_converter.py -v

# Unit tests de validación MIME
uv run pytest tests/unit/test_mime_validator.py -v

# Unit tests de formatos en settings
uv run pytest tests/unit/test_settings_formats.py -v

# Todos los unit tests
uv run pytest tests/unit/ -v
```
