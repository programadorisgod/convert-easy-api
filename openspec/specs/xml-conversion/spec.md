# XML Conversion Specification

## Purpose

Enable XML document conversion to JSON, YAML, CSV, HTML, and transformed XML formats using configurable mapping rules. Phase 3 capability reusing existing async job infrastructure.

## Processing Modes

| Mode | File Size | Behavior |
|------|-----------|----------|
| Sync | < 5MB | Stream response directly |
| Async | >= 5MB | Upload → Queue → Process → Download |

## Requirements

### Requirement: XML to JSON Conversion (Sync)

The system MUST convert XML documents to JSON format using the `xmltodict` library for files under 5MB. The converter SHALL support the following options: `preserve_attributes` (bool), `always_as_list` (bool), `dict_constructor` (dict). The response MUST return valid JSON with HTTP 200 and `Content-Type: application/json`.

#### Scenario: Valid XML to JSON conversion

- GIVEN a valid XML file under 5MB with MIME type `application/xml` or `text/xml`
- WHEN POST `/convert/xml/json` is called with file and options
- THEN the system SHALL return HTTP 200 with valid JSON body and `Content-Type: application/json`

#### Scenario: XML with namespaces preserved

- GIVEN an XML file containing namespace declarations
- WHEN conversion is performed with default options
- THEN namespace prefixes SHALL be preserved in the resulting JSON object

#### Scenario: Malformed XML rejected

- GIVEN an XML file containing invalid XML syntax
- WHEN POST `/convert/xml/json` is called
- THEN the system SHALL return HTTP 400 with error message "Malformed XML: {details}"

### Requirement: XML to YAML Conversion (Sync)

The system MUST convert XML documents to YAML format using the `yq` library for files under 5MB. The converter SHALL support indentation options (2/4 spaces) and flow style for nested structures. The response MUST return valid YAML with HTTP 200 and `Content-Type: application/x-yaml`.

#### Scenario: Valid XML to YAML conversion

- GIVEN a valid XML file under 5MB
- WHEN POST `/convert/xml/yaml` is called with file and `indent: 2`
- THEN the system SHALL return HTTP 200 with valid YAML and `Content-Type: application/x-yaml`

#### Scenario: YAML flow style for arrays

- GIVEN an XML file with repeating elements
- WHEN POST `/convert/xml/yaml` is called with `flow_style: true`
- THEN arrays SHALL be rendered in inline flow style `[item1, item2]`

### Requirement: XML to CSV Conversion (Async Required)

The system MUST convert XML documents to CSV format using `lxml` with explicit mapping configuration. The mapping configuration MUST define `root_element` (XPath) and `columns` array with `header` and `xpath` fields. Async mode SHALL be used for all CSV conversions regardless of file size.

#### Scenario: XML to CSV with explicit mapping

- GIVEN an XML file and valid mapping config `{"root_element": "//record", "columns": [{"header": "name", "xpath": "./name"}, {"header": "value", "xpath": "./@value"}]}`
- WHEN POST `/convert/xml/csv` is called
- THEN the system SHALL return HTTP 202 with `job_id` and process asynchronously
- AND the job SHALL complete with CSV file containing headers `name,value`

#### Scenario: Missing mapping configuration

- GIVEN an XML file without mapping configuration
- WHEN POST `/convert/xml/csv` is called
- THEN the system SHALL return HTTP 400 with error "Mapping configuration required for CSV conversion"

#### Scenario: Invalid XPath in mapping

- GIVEN an XML file with mapping containing invalid XPath expression
- WHEN conversion is attempted
- THEN the job SHALL fail with error "Invalid XPath in column mapping: {xpath}"

### Requirement: XML to HTML Conversion

The system MUST convert XML documents to HTML using XSLT transformation. Sync mode SHALL be used for files under 2MB; async mode for larger files. Built-in templates (`table`, `list`, `cards`) SHALL be available. Custom XSLT upload SHALL be supported in async mode.

#### Scenario: Built-in table template

- GIVEN a valid XML file under 2MB
- WHEN POST `/convert/xml/html` is called with `template: table`
- THEN the system SHALL return HTTP 200 with HTML table representation

#### Scenario: Custom XSLT stylesheet (async)

- GIVEN an XML file and valid XSLT stylesheet file
- WHEN POST `/convert/xml/html` is called with `xslt_file` and file size >= 2MB
- THEN the system SHALL return HTTP 202 with `job_id`
- AND process using the uploaded XSLT

#### Scenario: XSLT injection prevention

- GIVEN a malicious XSLT stylesheet attempting file system access
- WHEN conversion is attempted
- THEN the system SHALL reject with HTTP 400 "XSLT stylesheet validation failed"

### Requirement: XML to XML Transformation (Async)

The system MUST transform XML documents using XSLT to produce different XML structures. This operation SHALL be exclusively async and SHALL require XSLT file upload. The system SHALL validate XSLT syntax before queuing.

#### Scenario: Valid XSLT transformation

- GIVEN an XML file and valid XSLT stylesheet
- WHEN POST `/convert/xml/transform` is called
- THEN the system SHALL return HTTP 202 with `job_id`
- AND complete with transformed XML output

#### Scenario: Invalid XSLT rejected at queue time

- GIVEN an XML file and malformed XSLT stylesheet
- WHEN POST `/convert/xml/transform` is called
- THEN the system SHALL return HTTP 400 "Invalid XSLT: {parse error details}"

### Requirement: Common Validation

The system MUST enforce MIME type validation accepting only `application/xml` and `text/xml`. The system MUST enforce maximum file size of 50MB. The system MUST reject files exceeding this limit with HTTP 413.

#### Scenario: Invalid MIME type rejected

- GIVEN a file with content-type `application/json`
- WHEN uploaded to any `/convert/xml/*` endpoint
- THEN the system SHALL return HTTP 415 with "Unsupported media type for XML conversion"

#### Scenario: File size exceeded

- GIVEN an XML file of 51MB
- WHEN uploaded to any `/convert/xml/*` endpoint
- THEN the system SHALL return HTTP 413 with "File size exceeds maximum of 50MB"

## API Contract

### Endpoints

| Method | Path | Mode | Size Limit | Options |
|--------|------|------|------------|---------|
| POST | `/convert/xml/json` | Sync | 5MB | `preserve_attributes`, `always_as_list` |
| POST | `/convert/xml/yaml` | Sync | 5MB | `indent`, `flow_style` |
| POST | `/convert/xml/csv` | Async | 50MB | `mapping` (required) |
| POST | `/convert/xml/html` | Sync/Async | 2MB sync | `template` or `xslt_file` |
| POST | `/convert/xml/transform` | Async | 50MB | `xslt_file` (required) |

### Request Schema (Sync)

```json
{
  "file": "binary",
  "preserve_attributes": false,
  "always_as_list": false
}
```

### Request Schema (Async)

```json
{
  "job_id": "uuid",
  "mapping": {
    "root_element": "//xpath",
    "columns": [{"header": "name", "xpath": "./path"}]
  }
}
```

### Response Schema (Sync)

```json
{
  "content": "base64",
  "content_type": "application/json",
  "original_filename": "data.xml"
}
```

### Response Schema (Async)

```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Conversion queued"
}
```

## Error Scenarios

| Error | HTTP Code | Message Pattern |
|-------|-----------|----------------|
| Malformed XML | 400 | `Malformed XML: {expat_error}` |
| Missing mapping | 400 | `Mapping configuration required` |
| Invalid XPath | 400 | `Invalid XPath: {xpath}` |
| Invalid MIME | 415 | `Unsupported media type` |
| File too large | 413 | `File size exceeds maximum of {n}MB` |
| XSLT parse error | 400 | `Invalid XSLT: {details}` |

## Next Phase

Ready for design (sdd-design).
