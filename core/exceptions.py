"""
core/exceptions.py
Custom exception hierarchy for the FinSentry application.
"""


class FinSentryError(Exception):
    """Base exception for all FinSentry domain errors."""
    pass


class CSVFormatError(FinSentryError):
    """Raised when CSV structure, missing headers, or file access fails."""
    pass


class ValidationError(FinSentryError):
    """Base class for data validation failures."""
    pass


class InvalidRowError(ValidationError):
    """Raised when an individual CSV row contains invalid data.

    Attributes:
        line_number: Line in the CSV file (1-based, including header).
        field: Name of the column with the violation.
        reason: Plain-text explanation of why validation failed.
        raw_value: The exact string received from the file.
    """

    def __init__(self, line_number: int, field: str, reason: str, raw_value: str = ""):
        self.line_number = line_number
        self.field = field
        self.reason = reason
        self.raw_value = raw_value
        super().__init__(
            f"Line {line_number}: Invalid '{field}' -> {reason} (Received: {raw_value!r})"
        )
