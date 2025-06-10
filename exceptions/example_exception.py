from .base import AppException

class ExampleNotFoundException(AppException):
    def __init__(self, example_id: int):
        message = f"Example with ID {example_id} not found"
        super().__init__(message, status_code=404)

class ExampleAlreadyExistsException(AppException):
    def __init__(self, email: str):
        message = f"Example with email '{email}' already exists"
        super().__init__(message, status_code=409)

class ExampleCreationException(AppException):
    def __init__(self, details: str = "Failed to create example"):
        super().__init__(details, status_code=400)

class ExampleUpdateException(AppException):
    def __init__(self, example_id: int, details: str = "Failed to update example"):
        message = f"Failed to update example {example_id}: {details}"
        super().__init__(message, status_code=400)

class ExampleDeletionException(AppException):
    def __init__(self, example_id: int):
        message = f"Failed to delete example with ID {example_id}"
        super().__init__(message, status_code=400)