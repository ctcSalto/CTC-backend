from .base import AppException

class UserNotFoundException(AppException):
    def __init__(self, user_id: int):
        message = f"User with ID {user_id} not found"
        super().__init__(message, status_code=404)

class UserAlreadyExistsException(AppException):
    def __init__(self, user_id: int):
        message = f"User with ID {user_id} already exists"
        super().__init__(message, status_code=409)

class UserCreationException(AppException):
    def __init__(self):
        message = "User creation failed"
        super().__init__(message, status_code=409)

class UserUpdateException(AppException):
    def __init__(self, user_id: int):
        message = f"User with ID {user_id} already exists"
        super().__init__(message, status_code=409)

class UserDeletionException(AppException):
    def __init__(self, user_id: int):
        message = f"User with ID {user_id} already exists"
        super().__init__(message, status_code=409)
