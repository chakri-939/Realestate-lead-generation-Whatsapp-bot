"""
Custom Exception Classes — Bilingual WhatsApp RAG API
======================================================
Defines domain-specific exception types to replace raw string error messages
and enable structured, safe error handling across RAG API endpoints.
"""

class LuminaBaseError(Exception):
    """Base exception class for all RAG API errors."""
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class SQLSecurityViolation(LuminaBaseError):
    """Raised when generated or input SQL violates security constraints (e.g. DDL/DML injection)."""
    pass


class SQLGenerationError(LuminaBaseError):
    """Raised when the LLM engine fails to generate valid SQL code."""
    pass


class SQLExecutionError(LuminaBaseError):
    """Raised when DuckDB execution fails."""
    pass


class LLMConnectionError(LuminaBaseError):
    """Raised when connection to LLM service fails or times out."""
    pass


class InputValidationError(LuminaBaseError):
    """Raised when user input fails prompt length or content sanitization rules."""
    pass
