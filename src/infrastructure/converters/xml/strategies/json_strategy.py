"""XML to JSON conversion strategy using xmltodict."""

import json

import xmltodict

from .base import ConversionResult, XmlConversionStrategy
from ..exceptions import XmlSyntaxError, XmlValidationError
from ..schemas import XmlJsonOptions


class JsonStrategy(XmlConversionStrategy):
    """Converts XML to JSON using xmltodict."""

    def get_content_type(self) -> str:
        return "application/json"

    def validate_options(self, options: dict) -> None:
        """Validate JSON conversion options."""
        try:
            XmlJsonOptions(**options)
        except Exception as e:
            raise XmlValidationError(f"Invalid JSON options: {e}")

    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """
        Convert XML bytes to JSON.

        Args:
            xml_content: Raw XML bytes
            options: XmlJsonOptions dict

        Returns:
            ConversionResult with JSON content
        """
        try:
            # Parse options
            opts = XmlJsonOptions(**options) if options else XmlJsonOptions()

            # Parse XML to dict
            xml_str = xml_content.decode("utf-8")
            data = xmltodict.parse(
                xml_str,
                process_comments=True,
            )

            # Convert to JSON-compatible dict with options
            json_data = self._process_dict(
                data,
                preserve_attrs=opts.preserve_attributes,
                always_list=opts.always_as_list,
            )

            # Serialize to JSON
            json_str = json.dumps(
                json_data,
                indent=2,
                ensure_ascii=False,
            )

            return ConversionResult(
                content=json_str.encode("utf-8"),
                content_type="application/json",
                original_filename="",
                preserve_declaration=False,
            )

        except xmltodict.expat.ExpatError as e:
            raise XmlSyntaxError(f"Malformed XML: {e}")
        except UnicodeDecodeError as e:
            raise XmlSyntaxError(f"Invalid encoding: {e}")

    def _process_dict(
        self,
        data: dict | list,
        preserve_attrs: bool = False,
        always_list: bool = False,
    ) -> dict | list:
        """Process dict to handle xmltodict quirks."""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if not preserve_attrs and key.startswith("@"):
                    # Skip attributes unless explicitly preserved
                    continue

                processed_value = self._process_dict(
                    value,
                    preserve_attrs=preserve_attrs,
                    always_list=always_list,
                )

                # Handle repeated elements
                if (
                    always_list
                    and isinstance(processed_value, list)
                    and len(processed_value) == 1
                ):
                    result[key] = [processed_value[0]]
                else:
                    result[key] = processed_value

            return result
        elif isinstance(data, list):
            return [
                self._process_dict(item, preserve_attrs, always_list) for item in data
            ]
        else:
            return data
