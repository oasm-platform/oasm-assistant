import re

"""
Security utilities
"""

# SQL identifier validation pattern - only allow alphanumeric and underscore
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def validate_identifier(identifier: str, identifier_type: str = "identifier") -> str:
    """
    Validate SQL identifier (table/column name) to prevent SQL injection.

    Args:
        identifier: The identifier to validate
        identifier_type: Type of identifier for error message (e.g., "table name", "column name")

    Returns:
        Validated identifier

    Raises:
        ValueError: If identifier is invalid
    """
    if not identifier or not isinstance(identifier, str):
        raise ValueError(f"{identifier_type} must be a non-empty string")

    if not _VALID_IDENTIFIER.match(identifier):
        raise ValueError(
            f"Invalid {identifier_type} '{identifier}'. "
            f"{identifier_type.capitalize()}s must start with a letter or underscore and contain only "
            "alphanumeric characters and underscores."
        )

    if len(identifier) > 63:  # PostgreSQL identifier length limit
        raise ValueError(f"{identifier_type} too long (max 63 characters): '{identifier}'")

    return identifier