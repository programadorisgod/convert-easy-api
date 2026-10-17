# Guía MCP (Model Context Protocol) & Comparativa con CLI

Documento explicativo sobre qué es un MCP, su funcionamiento (online vs offline), y el análisis de valor al crear un **MCP** y una **CLI** para **Easy Convert API**.

---

## 1. ¿Qué es un MCP y para qué sirve?

**MCP** son las siglas de **Model Context Protocol** (Protocolo de Contexto de Modelos). Es un estándar abierto creado por Anthropic (e implementado por clientes como Claude Desktop, Cursor, Antigravity, Copilot, etc.) que permite conectar modelos de lenguaje (LLMs / Agentes) de manera estandarizada y segura con fuentes de datos, herramientas y sistemas externos.

### Analogía rápida: El puerto USB de la Inteligencia Artificial
Antes de MCP, para que un modelo de IA interactuara con una base de datos Postgres, una API externa o el sistema de archivos, cada interfaz o producto tenía que programar una integración ad-hoc y propietaria. Con MCP, escribes un solo **Servidor MCP** y cualquier cliente o agente de IA compatible puede descubrir y utilizar esas herramientas automáticamente.

### Principales capacidades de un MCP:
1. **Tools (Herramientas / Funciones):** Acciones que la IA puede invocar de forma autónoma (ej. *"convierte esta imagen a WebP"*, *"extrae el texto de este PDF"*).
2. **Resources (Recursos):** Datos estructurados o no estructurados que el agente puede leer (archivos locales, esquemas de BD, logs).
3. **Prompts:** Plantillas predefinidas que ayudan al agente a realizar flujos de trabajo específicos con ese servidor.

---

## 2. ¿Debe ser Online u Offline?

**Puede ser ambos.** La especificación de MCP contempla dos mecanismos principales de transporte:

### A. Modo Offline / Local (`stdio`)
- **Cómo opera:** El cliente de IA inicia el servidor MCP como un subproceso local en tu máquina usando la entrada/salida estándar (`stdio`).
- **Conectividad:** **No requiere internet**.
- **Ideal para:** Herramientas locales, interactuar con el sistema de archivos, bases de datos SQLite/Postgres locales, Docker o procesos locales de conversión.

### B. Modo Online / Remoto (`SSE` / HTTP o WebSockets)
- **Cómo opera:** El servidor MCP corre en un servidor remoto o contenedor en la nube. La comunicación se realiza vía HTTP con **Server-Sent Events (SSE)** o WebSockets.
- **Conectividad:** **Requiere internet**.
- **Ideal para:** Servicios multi-usuario, APIs en la nube (GitHub, Notion, Linear) o microservicios desplegados que no corren en la máquina del usuario final.

---

## 3. ¿Es útil hacerle un MCP y una CLI a Easy Convert API?

**Sí, es extremadamente útil para ambos**, porque cubren casos de uso complementarios:

### A. Utilidad de una CLI (`easy-convert-cli`)
Una CLI orientada a desarrolladores, DevOps y usuarios de terminal:
- **Automatización de scripts y pipelines CI/CD:** Optimizar imágenes automáticamente en un build, convertir markdown a PDF en un pre-commit hook o despliegue.
- **Flujo de trabajo ágil sin interfaz gráfica:** Convertir rápidamente un archivo desde la consola (`easy-convert img input.png -o output.webp --remove-bg`).
- **Procesamiento por lotes (batch processing):** Convertir carpetas enteras de documentos o vídeos en segundo plano.

### B. Utilidad de un MCP (`easy-convert-mcp`)
Un MCP orientado a que los **asistentes de IA / agentes** ejecuten conversiones autónomamente:
- **Flujos multimodales y agentes de desarrollo:** Cuando le dices a Cursor / Claude / Antigravity *"convierte este diagrama SVG a PNG para el README"* o *"extrae el texto de este PDF de especificaciones y pásamelo a Markdown"*, el agente llama al MCP directamente sin que tengas que abandonar el chat o abrir otra consola.
- **Procesamiento de contexto para LLMs:** Extraer páginas específicas de un PDF o convertir documentos a texto plano/markdown (`pymupdf4llm`) para alimentar el contexto del modelo.

---

## 4. Diferencia entre un MCP y una CLI

Aunque ambos pueden interactuar con los mismos endpoints de **Easy Convert API**, su público objetivo, interfaz y formato de datos son completamente distintos:

| Criterio | CLI (Command Line Interface) | MCP (Model Context Protocol) |
| :--- | :--- | :--- |
| **¿Quién lo usa?** | **Humanos** (desarrolladores, administradores de sistemas) o scripts de bash/CI. | **Modelos de Inteligencia Artificial / Agentes** (Claude, Cursor, Copilot, etc.). |
| **Entrada (Input)** | Banderas (`flags`), argumentos posicionales y stdin (`easy-convert -i doc.pdf -f docx`). | Esquemas JSON estructurados (`tool call` con JSON Schema validado por Pydantic/Zod). |
| **Salida (Output)** | Texto plano legible por humanos, barras de progreso, códigos de salida (`exit code 0/1`), colores terminal. | Respuestas JSON estructuradas (`content: [{ type: "text", text: "..." }]`, errores tipados). |
| **Descubrimiento** | Manual (el humano lee `--help` o `man`). | **Automático**: El agente inspecciona los schemas de las herramientas y decide cuál usar según el prompt. |
| **Toma de decisiones** | El usuario decide explícitamente cuándo y cómo ejecutar cada comando. | **El LLM decide** autónomamente qué herramienta llamar, con qué argumentos y cómo interpretar el resultado. |
| **Manejo de estados / Errores** | Errores en `stderr` con mensajes para humanos. | Mensajes de error contextuales para que el LLM pueda recuperarse, reintentar o corregir los parámetros. |

---

## 5. Arquitectura recomendada para Easy Convert

Para no duplicar lógica en el proyecto, la mejor práctica es:

```
                  ┌──────────────────────┐
                  │   Easy Convert API   │
                  │   (FastAPI / Core)   │
                  └──────────▲───────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
    ┌───────────────────┐         ┌───────────────────┐
    │  CLI (Typer/Rich) │         │    Servidor MCP   │
    │ (Para Humanos/CI) │         │ (Para LLMs/Agente)│
    └───────────────────┘         └───────────────────┘
```

1. **Core / SDK común:** Una librería cliente o llamadas a la API de FastAPI.
2. **CLI:** Con herramientas como `typer` y `rich` para formateo visual agradable al usuario humano.
3. **MCP Server:** Un servidor (usando el SDK oficial de Python `mcp` de Anthropic) que expone herramientas como:
   - `convert_image(input_path, target_format, remove_bg=False)`
   - `pdf_extract_text(pdf_path, pages=[])`
   - `convert_document(input_path, target_format)`
