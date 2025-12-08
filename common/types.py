"""Common types and enums for OASM Assistant"""

from enum import Enum


class QuestionType(str, Enum):
    """
    Question type classification for analysis routing.

    This enum defines the types of questions the system can handle,
    allowing LLM to select from predefined categories instead of generating free-form text.
    """

    # General knowledge questions (weather, education, facts, etc.)
    GENERAL_KNOWLEDGE = "general_knowledge"

    # Security-related questions (vulnerabilities, scans, threats, etc.)
    SECURITY_RELATED = "security_related"

    @classmethod
    def from_string(cls, value: str) -> "QuestionType":
        """
        Convert string to QuestionType enum.

        Args:
            value: String representation of question type

        Returns:
            QuestionType enum value

        Raises:
            ValueError: If value is not a valid QuestionType
        """
        try:
            return cls(value.lower().strip())
        except ValueError:
            raise ValueError(
                f"Invalid question type: {value}. "
                f"Valid types: {', '.join([qt.value for qt in cls])}"
            )

    @classmethod
    def list_values(cls) -> list[str]:
        """Get list of all valid question type values"""
        return [qt.value for qt in cls]

    def __str__(self) -> str:
        """String representation of enum"""
        return self.value

