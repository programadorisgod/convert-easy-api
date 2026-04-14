"""XML to YAML conversion strategy using pyyaml and yq CLI."""

import subprocess
from typing import Any

import xmltodict
import yaml

from .base import ConversionResult, XmlConversionStrategy
from ..exceptions import XmlSyntaxError, XmlValidationError, XmlConversionError
from ..schemas import XmlYamlOptions


class YamlStrategy(XmlConversionStrategy):
    """Converts XML to YAML using xmltodict + pyyaml/yq."""

    def get_content_type(self) -> str:
        return "application/x-yaml"

    def validate_options(self, options: dict) -> None:
        """Validate YAML conversion options."""
        try:
            XmlYamlOptions(**options)
        except Exception as e:
            raise XmlValidationError(f"Invalid YAML options: {e}")

    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """
        Convert XML bytes to YAML.

        Uses yq CLI if available (better formatting), falls back to pyyaml.
        """
        try:
            opts = XmlYamlOptions(**options) if options else XmlYamlOptions()

            # First convert to dict (like JSON strategy)
            xml_str = xml_content.decode("utf-8")
            data = xmltodict.parse(xml_str, process_comments=True)

            # Try yq first (better output), fallback to pyyaml
            try:
                yaml_str = self._convert_with_yq(data, opts)
            except (FileNotFoundError, subprocess.CalledProcessError):
                yaml_str = self._convert_with_pyyaml(data, opts)

            # Prepend XML declaration if requested
            if opts.preserve_xml_declaration:
                yaml_str = f'<?xml version="1.0" encoding="UTF-8"?>\n{yaml_str}'

            return ConversionResult(
                content=yaml_str.encode("utf-8"),
                content_type="application/x-yaml",
                original_filename="",
                preserve_declaration=opts.preserve_xml_declaration,
            )

        except xmltodict.expat.ExpatError as e:
            raise XmlSyntaxError(f"Malformed XML: {e}")
        except UnicodeDecodeError as e:
            raise XmlSyntaxError(f"Invalid encoding: {e}")

    def _convert_with_yq(self, data: dict, opts: XmlYamlOptions) -> str:
        """Convert using yq CLI for better formatting."""
        import json

        # Convert dict to JSON, pipe to yq
        json_str = json.dumps(data, ensure_ascii=False)

        # Determine yq style flags
        indent = opts.indent
        style = "flow" if opts.flow_style else "block"

        result = subprocess.run(
            ["yq", "-o", "yaml", "-I", str(indent), "-s", style],
            input=json_str,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout

    def _convert_with_pyyaml(self, data: dict, opts: XmlYamlOptions) -> str:
        """Fallback conversion using pyyaml."""
        return yaml.dump(
            data,
            indent=opts.indent,
            allow_unicode=True,
            default_flow_style=opts.flow_style,
            sort_keys=False,
        )
