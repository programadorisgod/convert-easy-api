# Tasks: XML Conversion Feature

## Phase 1: Infrastructure

- [ ] 1.1 Add `lxml>=4.9.0`, `xmltodict>=0.13.0`, `pyyaml>=6.0` to `pyproject.toml` dependencies — XML processing libraries required by all strategies
- [ ] 1.2 Create `src/infrastructure/converters/xml/exceptions.py` with `XmlConversionError`, `XmlSyntaxError`, `XmlMappingError`, `XmlXsltError`, `XmlSizeError`, `XmlMimeError` extending `ProcessingError` — match existing exception patterns in `shared/exceptions.py`
- [ ] 1.3 Create `src/infrastructure/converters/xml/strategies/base.py` with `ConversionResult` dataclass and `XmlConversionStrategy` ABC — defines interface all strategies must implement

## Phase 2: Core Implementation

- [x] 2.1 Create `src/infrastructure/converters/xml/schemas.py` with Pydantic models: `XmlJsonRequest`, `XmlYamlRequest`, `XmlCsvRequest`, `XmlHtmlRequest`, `XmlTransformRequest` — request validation per endpoint
- [x] 2.2 Create `src/infrastructure/converters/xml/strategies/json_strategy.py` using `xmltodict` — implements `preserve_attributes`, `always_as_list` options
- [x] 2.3 Create `src/infrastructure/converters/xml/strategies/yaml_strategy.py` using `pyyaml` — implements `indent` (2/4), `flow_style` options
- [x] 2.4 Create `src/infrastructure/converters/xml/strategies/csv_strategy.py` using `lxml` with XPath — required `mapping` config, flatten nested paths with `_` separator
- [x] 2.5 Create `src/infrastructure/converters/xml/strategies/html_strategy.py` using `lxml` + built-in templates — implements `template` (table/list/cards), custom XSLT support
- [x] 2.6 Create `src/infrastructure/converters/xml/strategies/xslt_strategy.py` using `lxml` — sandboxed transformation via `strip_elements`, pre-queue validation
- [x] 2.7 Create `src/infrastructure/converters/xml/strategies/__init__.py` exporting all strategies — enables clean imports
- [x] 2.8 Create `src/infrastructure/converters/xml_converter.py` with `XmlConverter` orchestrator — factory method for strategy selection, sync path (<5MB JSON/YAML, <2MB HTML) vs async path (>=5MB, CSV/XSLT)
- [x] 2.9 Create `src/infrastructure/converters/xml/__init__.py` exporting `XmlConverter` — package initialization
- [x] 2.10 Modify `src/infrastructure/converters/__init__.py` to export `XmlConverter` — integrate with existing converter module

## Phase 3: Controller

- [ ] 3.1 Create `src/interfaces/http/controllers/xml_conversion_controller.py` with endpoints: `POST /convert/xml/json` (sync <5MB), `POST /convert/xml/yaml` (sync <5MB), `POST /convert/xml/csv` (async always), `POST /convert/xml/html` (sync <2MB), `POST /convert/xml/transform` (async always) — follow `image_processing_controller.py` patterns

## Phase 4: Worker Integration

- [x] 4.1 Modify `src/infrastructure/worker/conversion_worker.py` to add XML job handler — detect `xml_config` in job data, call `XmlConverter.convert()`, handle XML-specific errors

## Phase 5: Testing

- [ ] 5.1 Create `tests/unit/converters/xml/test_strategies.py` — unit tests for each strategy with mock XML input, verify output format/structure
- [ ] 5.2 Create `tests/unit/converters/xml/test_xml_converter.py` — unit tests for `XmlConverter` strategy selection logic, size thresholds
- [ ] 5.3 Create `tests/integration/test_xml_endpoints.py` — integration tests for all endpoints, verify HTTP codes, content types, error cases (malformed XML, invalid XSLT, oversized files)
