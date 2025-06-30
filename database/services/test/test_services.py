from database.models.test.author import Author
from database.models.test.post import Post
from database.services.filter.filters import BaseServiceWithFilters

# Servicio para Author
class AuthorService(BaseServiceWithFilters[Author]):
    def __init__(self):
        super().__init__(Author)

# Servicio para Post  
class PostService(BaseServiceWithFilters[Post]):
    def __init__(self):
        super().__init__(Post)