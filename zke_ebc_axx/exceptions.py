class ZKEError(Exception):
    """Base exception for all ZKE EBC-Axx related errors."""
    pass

class CommunicationError(ZKEError):
    """Exception raised for communication errors."""
    pass

class CommandError(ZKEError):
    """Exception raised when a command fails."""
    pass

class TimeoutError(ZKEError):
    """Exception raised when a command times out."""
    pass
