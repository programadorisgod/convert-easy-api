# Proposal: XML Conversion

## Intent

Add XML conversion capability to support structured data interchange. Unlike image/document formats with fixed semantics, XML requires **generic mapping** — any XML → JSON/YAML/CSV/HTML via configurable rules. This is a Phase 3 capability that reuses existing job infrastructure.

## Scope

### In Scope
- XML → JSON conversion (using `xmltodict`)
- XML → YAML conversion (using `yq`)
- XML → CSV conversion (using `lxml` + custom tabular extractor)
- XML → HTML conversion (using XSLT)
- XML → XML transform (using XSLT)
- Sync mode for files under configurable size threshold (default: 1MB)
- Async mode (upload → queue → process → download) for larger files
- Generic mapping configuration per conversion target

### Out of Scope
- XML schema validation (Phase N)
- Streaming XML parsing for very large files (>100MB)
- XML-specific UI/file picker (handled at client level)
- Bidirectional conversions (JSON→XML as separate feature)

## Capabilities

### New Capabilities
- `xml-conversion`: Full XML conversion pipeline supporting multiple output formats with configurable mapping rules

### Modified Capabilities
- None (new capability only)

## Approach

### Architecture
```
src/
├── infrastructure/converters/xml_converter.py
├── interfaces/http/controllers/xml_processing_controller.py
└── application/{commands,handlers}.py  (modified)
```

### Tool Selection
| Conversion | Tool | Rationale |
|------------|------|-----------|
| XML → JSON | `xmltodict` | Namespaces, attrs, arrays |
| XML → YAML | `yq` | jq-style interface |
| XML → CSV | `lxml` + custom | Custom tabular extraction |
| XML → HTML/XML | XSLT | Standard, declarative transforms |

### Sync vs Async
- **Sync**: Files < `max_sync_xml_size_kb` (default 1024KB) — stream response
- **Async**: Files ≥ threshold — full BullMQ pipeline

## Affected Areas

| Area | Impact |
|------|--------|
| `src/infrastructure/converters/` | New `xml_converter.py` |
| `src/interfaces/http/controllers/` | New `xml_processing_controller.py` |
| `src/application/{commands,handlers}.py` | Modified |
| `shared/config/settings.py` | Modified |
| `src/interfaces/http/controllers/job_controller.py` | Modified |

## Risks

| Risk | Mitigation |
|------|------------|
| Complex namespaces | Document behavior; warn in response |
| XSLT injection | Validate stylesheet; sandbox execution |
| Large XML memory | 50MB max; streaming for >100MB |
| Ambiguous CSV extraction | Require explicit mapping config |

## Rollback Plan

1. Delete `xml_converter.py`, `xml_processing_controller.py`
2. Remove `ProcessXmlCommand`/`ProcessXmlHandler` from app layer
3. Remove XML fields from `settings.py`
4. Deploy — no breaking changes (endpoints added only)

## Dependencies

- `xmltodict>=0.13.0`, `lxml>=4.9.0`, `yq>=3.0.0`
- Existing BullMQ infrastructure (reused)

## Success Criteria

- [ ] All 5 conversion paths produce valid output
- [ ] Sync <2s for files under threshold
- [ ] Async completes with proper state transitions
- [ ] Clear errors for malformed XML
- [ ] Namespaces preserved in output
- [ ] XSLT stylesheets sandboxed
