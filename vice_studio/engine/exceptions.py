"""Custom exceptions for the Vice Studio engine."""


class ViceStudioError(Exception):
    """Base exception for Vice Studio engine failures."""


class AgentExecutionError(ViceStudioError):
    """Raised when an agent cannot complete its execution."""


class ResourceNotFoundError(ViceStudioError):
    """Raised when a required file or directory cannot be found."""


class ConfigurationError(ViceStudioError):
    """Raised when a configuration file is missing or invalid."""
