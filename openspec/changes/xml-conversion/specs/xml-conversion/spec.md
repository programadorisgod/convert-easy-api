# Delta for xml-conversion

## ADDED Requirements

### Requirement: XML to JSON Conversion (Sync)

The system MUST convert XML documents to JSON format using the `xmltodict` library for files under 5MB. The converter SHALL support options `preserve_attributes`, `always_as_list`, and `dict_constructor`. The response MUST return valid JSON with HTTP 200.

#### Scenario: Valid XML to JSON conversion

- GIVEN a valid XML file under 5MB with MIME type `application/xml` or `text/xml`
- WHEN POST `/convert/xml/json` is called with file and options
- THEN the system SHALL return HTTP 200 with valid JSON body

#### Scenario: Malformed XML rejected

- GIVEN an XML file containing invalid XML syntax
- WHEN POST `/convert/xml/json` is called
- THEN the system SHALL return HTTP 400 with error "Malformed XML"

### Requirement: XML to YAML Conversion (Sync)

The system MUST convert XML documents to YAML format using `yq` for files under 5MB with configurable indentation and flow style.

#### Scenario: Valid XML to YAML conversion

- GIVEN a valid XML file under 5MB
- WHEN POST `/convert/xml/yaml` is called with `indent: 2`
- THEN the system SHALL return HTTP 200 with valid YAML

### Requirement: XML to CSV Conversion (Async Required)

The system MUST convert XML to CSV using explicit mapping configuration. Async mode is REQUIRED for all CSV conversions.

#### Scenario: XML to CSV with mapping

- GIVEN valid mapping config `{"root_element": "//record", "columns": [{"header": "name", "xpath": "./name"}]}`
- WHEN POST `/convert/xml/csv` is called
- THEN the system SHALL return HTTP 202 with `job_id`

### Requirement: XML to HTML Conversion

The system MUST convert XML to HTML using XSLT. Sync for <2MB, async for larger. Built-in templates and custom XSLT upload supported.

#### Scenario: Built-in table template

- GIVEN valid XML file under 2MB
- WHEN POST `/convert/xml/html` is called with `template: table`
- THEN the system SHALL return HTTP 200 with HTML table

### Requirement: XML to XML Transformation (Async)

The system MUST transform XML using XSLT. Exclusively async, requires XSLT file upload.

#### Scenario: Valid XSLT transformation

- GIVEN XML file and valid XSLT stylesheet
- WHEN POST `/convert/xml/transform` is called
- THEN the system SHALL return HTTP 202 with `job_id`

### Requirement: Common XML Validation

The system MUST validate MIME types (`application/xml`, `text/xml`) and enforce 50MB max file size.

#### Scenario: Invalid MIME rejected

- GIVEN file with `application/json` content-type
- WHEN uploaded to `/convert/xml/*`
- THEN the system SHALL return HTTP 415

#### Scenario: File size exceeded

- GIVEN XML file exceeding 50MB
- WHEN uploaded to `/convert/xml/*`
- THEN the system SHALL return HTTP 413

## API Contract

| Method | Path | Mode | Size |
|--------|------|------|------|
| POST | `/convert/xml/json` | Sync | 5MB |
| POST | `/convert/xml/yaml` | Sync | 5MB |
| POST | `/convert/xml/csv` | Async | 50MB |
| POST | `/convert/xml/html` | Sync/Async | 2MB sync |
| POST | `/convert/xml/transform` | Async | 50MB |

## Next Phase

Ready for design (sdd-design).
