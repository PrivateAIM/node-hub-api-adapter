"""Custom exceptions raised by this module."""


class ConfigError(Exception):
    """Raised when a config file is invalid."""

    def __init__(self, option: str, value: str):
        super().__init__(f"Invalid value for {option}: {value}")
