# Sistema de Logs y Manejo de Errores — Easy Convert API

Este documento detalla la arquitectura de registro (logging), la estrategia de manejo seguro de errores y la política de retención automática de logs en **Easy Convert API**.

---

## 1. Filosofía y Objetivos

El sistema está diseñado bajo el principio de **Privacidad y Seguridad por Diseño (Defense in Depth / CWE-209 Mitigation)**:

1. **Cero Fuga de Información Técnica al Cliente**: El cliente o usuario final nunca recibe rutas internas (`/tmp/`, `/app/src/...`), binarios de sistema (`magick`, `ffmpeg`), códigos de salida de subprocesos ni tracebacks de Python.
2. **Máxima Visibilidad para el Desarrollador**: Cada fallo queda registrado con el comando exacto ejecutado, salida estándar y de error (`stderr`), código de retorno y traceback completo.
3. **Correlación Unificada (Traceability)**: Cada petición HTTP y cada tarea en background (*worker*) tiene asignado un identificador único (`request_id` y `job_id`) que se propaga a lo largo de todo el ciclo de vida.
4. **Retención Automática (3 Días)**: Rotación automática diaria y purga de logs antiguos para evitar consumo innecesario de disco y respetar la privacidad.

---

## 2. Arquitectura de Dos Niveles (Two-Tier Error Handling)

```
                       Petición del Usuario
                               │
                               ▼
                    [RequestIdMiddleware]
                Asigna X-Request-ID único
                               │
                               ▼
                   [Pipeline de Conversión]
                               │
            ┌──────────────────┴──────────────────┐
        ¿Éxito?                               ¿Fallo?
            │                                     │
    Respuesta 200 OK                       [AppError / Exception]
                                                  │
                                   ┌──────────────┴──────────────┐
                                   ▼                             ▼
                        Nivel Cliente (Público)        Nivel Servidor (Privado)
                        -----------------------        ------------------------
                        - Mensaje sanitizado           - Log completo estructurado
                        - Sin rutas ni tracebacks      - [req_id] [job_id] context
                        - request_id de referencia     - stderr, cmd y stacktrace
                        - Status HTTP adecuado         - Escrito a logs/errors.log
```

### Nivel 1: Lo que ve el Usuario / Cliente

El API responde con un formato JSON limpio y uniforme:

```json
{
  "error": "Error al procesar el archivo.",
  "request_id": "req_8f1b2c3d4e5a"
}
```

En la cabecera HTTP de la respuesta siempre se incluye:
```http
X-Request-ID: req_8f1b2c3d4e5a
```

Si el usuario reporta un problema, solo necesita proporcionar el código de referencia `req_...` para que el desarrollador pueda rastrear el incidente exacto sin que el usuario haya visto datos sensibles del servidor.

### Nivel 2: Lo que ve el Desarrollador (Logs Internos)

En `logs/errors.log` y en la consola del servidor se registra el fallo con contexto completo:

```text
2026-10-16 18:25:31,412 [ERROR] [EasyConvertAPI] [req_8f1b2c3d4e5a] [job_b72e1a9c] src.infrastructure.converters.image_converter: Conversion failed: ImageMagick command failed with code 1.
Technical details: Command: magick convert /tmp/input.png -quality 85 /tmp/output.avif
Stderr: magick: delegate failed 'heif-enc -o "%o" "%i"' @ error/delegate.c/InvokeDelegate/1924.
Traceback (most recent call last):
  File "src/infrastructure/converters/image_converter.py", line 125, in convert
    ...
```

---

## 3. Almacenamiento y Archivos de Log

Los logs se guardan de forma predeterminada en la carpeta `logs/` de la raíz del proyecto (o la ruta configurada en `LOG_DIR`):

| Archivo | Nivel Mínimo | Contenido |
|---------|--------------|-----------|
| `logs/api.log` | `INFO` | Todas las operaciones generales: inicio de API, peticiones procesadas, jobs iniciados y finalizados. |
| `logs/errors.log` | `ERROR` | Exclusivamente errores, excepciones no controladas y fallos de conversión con su stack trace y `technical_details`. |
| `Consola (Stdout)` | `INFO` | Mismo formato con prefijos de correlación `[req_...] [job_...]` para fácil inspección con `docker logs`. |

---

## 4. Política de Retención y Rotación (Eliminación cada 3 Días)

La rotación de logs está implementada con la clase `TimedRotatingFileHandler` de la librería estándar de Python:

- **Frecuencia de Rotación**: Diaria a medianoche (`when="midnight"`, `interval=1`).
- **Retención (`backupCount`)**: `3` (Configurable vía variable de entorno `LOG_RETENTION_DAYS`).
- **Mecanismo de Purga**: Al llegar la medianoche, Python renombra el archivo actual (por ejemplo, `api.log.2026-10-15`) y borra automáticamente cualquier archivo histórico que supere los 3 días de antigüedad.
- **Sin Dependencias Externas**: No requiere configurar `logrotate`, tareas `cron` ni daemons adicionales del sistema operativo.

### Ejemplo de ciclo de vida de archivos:

```text
logs/
├── api.log                  # Archivo del día actual
├── api.log.2026-10-15       # Ayer (Día -1)
├── api.log.2026-10-14       # Anteayer (Día -2)
├── api.log.2026-10-13       # Hace 3 días (Día -3) -> Se eliminará en la siguiente rotación
├── errors.log               # Errores del día actual
├── errors.log.2026-10-15
├── errors.log.2026-10-14
└── errors.log.2026-10-13
```

---

## 5. Variables de Entorno

Puedes personalizar el comportamiento en tu archivo `.env` o en el entorno del contenedor:

```env
# Directorio donde se almacenarán los archivos de logs
LOG_DIR=logs

# Días de retención antes de eliminación automática (predeterminado: 3)
LOG_RETENTION_DAYS=3

# Nivel de log para consola y api.log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

---

## 6. Guía Práctica de Depuración (Debugging)

### Buscar un error por ID de Referencia del Usuario

Cuando un usuario reporte un fallo con referencia `Ref: req_a1b2c3d4`:

```bash
# Buscar en el log de errores
grep "req_a1b2c3d4" logs/errors.log

# O buscar en todos los logs (incluyendo rotados)
zgrep -h "req_a1b2c3d4" logs/errors.log* logs/api.log*
```

### Seguir logs en tiempo real en desarrollo

```bash
# Ver solo errores con contexto
tail -f logs/errors.log

# Ver todo el flujo de la API
tail -f logs/api.log
```

### En Contenedores Docker / Podman

Si la API corre en Docker, puedes inspeccionar directamente la consola o ingresar al volumen:

```bash
# Ver logs con correlación en Docker
docker logs -f easy-convert-api

# Filtrar por un request ID específico en Docker
docker logs easy-convert-api 2>&1 | grep "req_a1b2c3d4"

# Ver los archivos de log dentro del contenedor
docker exec -it easy-convert-api tail -n 50 /app/logs/errors.log
```

---

## 7. Módulos Clave del Sistema

- [`shared/config/settings.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/shared/config/settings.py): Definición de `log_dir` y `log_retention_days`.
- [`shared/exceptions.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/shared/exceptions.py): Clase base `AppError`, función `sanitize_user_error_message` y excepciones de dominio.
- [`src/infrastructure/logging/context.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/src/infrastructure/logging/context.py): ContextVars de Python para correlación asíncrona de `request_id` y `job_id`.
- [`src/infrastructure/logging/setup.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/src/infrastructure/logging/setup.py): Configuración de formatters y handlers con rotación diaria y retención de 3 días.
- [`src/infrastructure/logging/middleware.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/src/infrastructure/logging/middleware.py): Middleware HTTP para captura e inyección de `X-Request-ID`.
- [`src/interfaces/http/exception_handlers.py`](file:///home/camidev/Documentos/development/side-projects/convert-easy-api/src/interfaces/http/exception_handlers.py): Handlers globales que devuelven respuestas limpias a los clientes y vuelcan los detalles al log.
