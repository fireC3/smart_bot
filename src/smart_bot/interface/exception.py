

class ResponseLengthExceedException(Exception):
    """Exception raised when the output response length exceeds the model's maximum limit."""
    def __init__(self, message="The output response length exceeds the model's maximum limit."):
        super().__init__(message)