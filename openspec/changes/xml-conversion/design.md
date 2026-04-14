# Design: XML Conversion

## Technical Approach

Implement XML conversion capability as a **Strategy-pattern converter** following the existing `DocumentConverter` architecture. Each output format (JSON, YAML, CSV, HTML, XSLT) gets its own strategy class, with the `XmlConverter` orchestrator selecting and executing the appropriate strategy based on the requested output format.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pattern | Strategy (GoF) | Each format needs different parsing logic; strategies encapsulate format-specific behavior. Enables easy addition of new formats. |
| Sync vs Async threshold | 5MB (JSON/YAML), 2MB (HTML), Async-only (CSV/XSLT) | Per spec requirements. Smaller threshold for HTML due to XSLT processing overhead. |
| XSLT validation | Pre-queue validation | Reject invalid XSLT early with HTTP 400 instead of queuing a doomed job. |
| CSV mapping | Required config | Flat tabular output requires explicit XPath mapping; no sensible defaults exist. |
| XSLT security | Sandboxed transformation | Prevent `document()`, `xsl:import` attacks via lxml's `strip_elements`. |

## Directory Structure

```
src/infrastructure/converters/
├── xml_converter.py              # Main orchestrator + factory
├── xml/
│   ├── __init__.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py               # XmlConversionStrategy (ABC)
│   │   ├── json_strategy.py      # xmltodict-based
│   │   ├── yaml_strategy.py      # pyyaml-based
│   │   ├── csv_strategy.py       # lxml + explicit mapping
│   │   ├── html_strategy.py      # Built-in templates + custom XSLT
│   │   └── xslt_strategy.py      # XSLT transformation
│   ├── schemas.py                 # Pydantic models
│   └── exceptions.py              # XML-specific errors

src/interfaces/http/controllers/
└── xml_conversion_controller.py   # FastAPI endpoints

tests/
├── unit/
│   └── converters/
│       └── xml/
│           ├── test_strategies.py
│           └── test_xml_converter.py
└── integration/
    └── test_xml_endpoints.py
```

## Data Flow

```
Request ──► Controller ──► [Sync Path] ──► XmlConverter ──► Strategy ──► Response
                │                                                      │
                └──► [Async Path] ──► Job Queue ──► Worker ──────────┘
```

### Sync Path (< 5MB)
1. Controller validates MIME type and file size
2. `XmlConverter.convert()` called directly with file bytes
3. Strategy selected by output format, executed synchronously
4. Result returned as base64-encoded response

### Async Path (>= 5MB or CSV/XSLT)
1. Controller validates and returns HTTP 202 with `job_id`
2. Job queued with XML config and options
3. Worker picks up job, calls `XmlConverter.convert()` 
4. Result stored, client polls via `/jobs/{job_id}`

## Class Design

```python
# src/infrastructure/converters/xml/strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ConversionResult:
    content: bytes
    content_type: str
    original_filename: str

class XmlConversionStrategy(ABC):
    """Base strategy for XML conversion formats."""
    
    @abstractmethod
    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """Convert XML to target format."""
        ...
    
    @abstractmethod
    def validate_options(self, options: dict) -> None:
        """Validate format-specific options. Raises ValidationError."""
        ...
```

### Strategy Implementations

| Strategy | Library | Key Options |
|---------|---------|-------------|
| `JsonStrategy` | `xmltodict` | `preserve_attributes`, `always_as_list`, `dict_constructor` |
| `YamlStrategy` | `pyyaml` | `indent` (2/4), `flow_style` |
| `CsvStrategy` | `lxml` | `mapping` (required: root_element, columns[]) |
| `HtmlStrategy` | `lxml` + templates | `template` (table/list/cards), `xslt_file` |
| `XsltStrategy` | `lxml` | `xslt_content` (required) |

## API Integration

### Controller Pattern (per `image_processing_controller.py`)

```python
# src/interfaces/http/controllers/xml_conversion_controller.py
from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter(prefix="/convert/xml", tags=["XML Conversion"])

# Endpoints per spec:
# POST /convert/xml/json  - Sync, <5MB
# POST /convert/xml/yaml  - Sync, <5MB  
# POST /convert/xml/csv   - Async always
# POST /convert/xml/html  - Sync <2MB, Async >=2MB
# POST /convert/xml/transform - Async always
```

### Request Validation

```python
class XmlJsonRequest(BaseModel):
    preserve_attributes: bool = False
    always_as_list: bool = False

class XmlCsvRequest(BaseModel):
    root_element: str  # XPath, required
    columns: list[ColumnMapping]
    
class ColumnMapping(BaseModel):
    header: str
    xpath: str  # Relative XPath from root_element

class XmlHtmlRequest(BaseModel):
    template: str | None = "table"  # table, list, cards
    xslt_file: UploadFile | None = None  # Custom XSLT (async only)

class XmlTransformRequest(BaseModel):
    xslt_file: UploadFile  # Required
```

## Error Handling

| Exception | HTTP Code | Used When |
|-----------|-----------|-----------|
| `XmlSyntaxError` | 400 | Malformed XML, expat parse failures |
| `XmlMappingError` | 400 | Invalid XPath in CSV mapping |
| `XmlXsltError` | 400 | XSLT parse/transformation errors |
| `XmlSizeError` | 413 | File >50MB |
| `XmlMimeError` | 415 | Non-XML MIME type |
| `XmlValidationError` | 400 | Missing required options |

```python
# src/infrastructure/converters/xml/exceptions.py
class XmlConversionError(ProcessingError):
    """Base XML conversion error."""
    pass

class XmlSyntaxError(XmlConversionError):
    """Malformed XML document."""
    
class XmlMappingError(XmlConversionError):
    """Invalid mapping configuration."""
    
class XmlXsltError(XmlConversionError):
    """XSLT validation or transformation failed."""
    
class XmlSizeError(XmlConversionError):
    """File exceeds size limit."""
```

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    ...
    "lxml>=4.9.0",        # XML/HTML/XSLT processing
    "xmltodict>=0.13.0",  # XML → dict → JSON
    "pyyaml>=6.0",        # YAML output
]
```

| Library | Purpose | Why Not Alternatives |
|---------|---------|---------------------|
| `lxml` | XPath, XSLT, HTML serialization | Industry standard; `xml.etree` lacks XSLT |
| `xmltodict` | XML → JSON | Battle-tested, handles namespaces well |
| `pyyaml` | YAML serialization | Safe (no arbitrary code exec) |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/infrastructure/converters/xml_converter.py` | Create | Main converter orchestrator |
| `src/infrastructure/converters/xml/__init__.py` | Create | Package init |
| `src/infrastructure/converters/xml/strategies/__init__.py` | Create | Strategy exports |
| `src/infrastructure/converters/xml/strategies/base.py` | Create | Abstract base class |
| `src/infrastructure/converters/xml/strategies/json_strategy.py` | Create | JSON conversion |
| `src/infrastructure/converters/xml/strategies/yaml_strategy.py` | Create | YAML conversion |
| `src/infrastructure/converters/xml/strategies/csv_strategy.py` | Create | CSV conversion |
| `src/infrastructure/converters/xml/strategies/html_strategy.py` | Create | HTML conversion |
| `src/infrastructure/converters/xml/strategies/xslt_strategy.py` | Create | XSLT transformation |
| `src/infrastructure/converters/xml/schemas.py` | Create | Pydantic models |
| `src/infrastructure/converters/xml/exceptions.py` | Create | XML-specific exceptions |
| `src/infrastructure/converters/__init__.py` | Modify | Export `XmlConverter` |
| `src/interfaces/http/controllers/xml_conversion_controller.py` | Create | API endpoints |
| `src/infrastructure/worker/conversion_worker.py` | Modify | Add XML job handler |
| `pyproject.toml` | Modify | Add dependencies |
| `tests/unit/converters/xml/` | Create | Unit tests |
| `tests/integration/test_xml_endpoints.py` | Create | Integration tests |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Each strategy | Mock XML input, verify output format/structure |
| Unit | XmlConverter | Test strategy selection logic |
| Unit | Schemas | Validate option combinations |
| Integration | All endpoints | Real files, verify HTTP codes and content types |
| Integration | Error cases | Malformed XML, invalid XSLT, oversized files |

## Resolved Questions

| Question | Decision | Implementation |
|----------|----------|----------------|
| Streaming responses for large sync | ✅ YES | Use `StreamingResponse` with generators for files >1MB |
| Preserve `<?xml ?>` declaration | ✅ YES | Configurable per strategy, default ON for XML→XML |
| CSV nested elements | ✅ FLATTEN | Flatten nested paths with `_` separator (e.g., `parent_child_value`) |

### Streaming Implementation

```python
async def stream_conversion(xml_bytes: bytes, strategy: XmlConversionStrategy):
    """Stream conversion output for large files."""
    buffer = BytesIO()
    # Process in chunks
    for chunk in process_chunks(xml_bytes):
        result = strategy.convert(chunk)
        buffer.write(result.content)
        yield result.content
```

### CSV Flattening Rules

```
XML Structure:
<record>
  <customer>
    <name>John</name>
  </customer>
  <order>123</order>
</record>

CSV Output (flattened):
customer_name,order
John,123
```
