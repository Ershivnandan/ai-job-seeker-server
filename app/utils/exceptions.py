class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ResumeParseError(AppException):
    def __init__(self, message: str = "Failed to parse resume"):
        super().__init__(message, status_code=422)


class ScraperError(AppException):
    def __init__(self, message: str = "Scraping operation failed"):
        super().__init__(message, status_code=502)


class LLMError(AppException):
    def __init__(self, message: str = "LLM request failed"):
        super().__init__(message, status_code=502)


class PlatformAuthError(AppException):
    def __init__(self, message: str = "Platform authentication failed"):
        super().__init__(message, status_code=401)
