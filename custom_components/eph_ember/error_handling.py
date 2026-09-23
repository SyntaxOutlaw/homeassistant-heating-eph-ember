"""Domain errors for the EPH Controls integration."""


class EmberError(Exception):
    """Base error for EPH Ember domain failures."""


class InvalidCredentials(EmberError):
    """Username/password or token refresh failed."""


class EmberApiError(EmberError):
    """The EMBER cloud API returned an unexpected error."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ZoneNotFound(EmberError):
    """A requested zone was not present in the last poll."""
