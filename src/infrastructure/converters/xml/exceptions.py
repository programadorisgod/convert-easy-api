"""XML conversion exceptions."""

from shared.exceptions import ProcessingError


class XmlConversionError(ProcessingError):
    """Base exception for XML conversion errors."""

    pass


class XmlSyntaxError(XmlConversionError):
    """Raised when XML document is malformed."""

    pass


class XmlMappingError(XmlConversionError):
    """Raised when CSV/XSLT mapping configuration is invalid."""

    pass


class XmlXsltError(XmlConversionError):
    """Raised when XSLT validation or transformation fails."""

    pass


class XmlSizeError(XmlConversionError):
    """Raised when file exceeds size limit."""

    pass


class XmlMimeError(XmlConversionError):
    """Raised when file MIME type is not XML."""

    pass


class XmlValidationError(XmlConversionError):
    """Raised when required options are missing or invalid."""

    pass
