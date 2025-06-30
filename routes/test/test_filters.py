from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session
from database.models.test.author import AuthorResponse
from database.services.filter.filters import Filter
from database.services.filter.filters import QueryBuilderError
from database.database import Services, get_services, get_session

from utils.logger import show

router = APIRouter(prefix="/test", tags=["Test"])

@router.post("/users", response_model=list[AuthorResponse], status_code=status.HTTP_200_OK)
async def get_users(
    filters: Filter = Depends(),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
    #current_user: User = Depends(get_current_active_user)
):
    try:
        show(filters)
        authors = services.authorService.get_with_filters(session, filters)
        return authors
    except QueryBuilderError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


"""
curl -X 'POST' \
  'http://127.0.0.1:8000/test/users?logical_operator=and&limit=10&offset=0&order_direction=asc' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "conditions": [
    {
      "attribute": "username",
      "operator": "eq",
      "value": "PRUEBA"
    },
    {
      "attribute": "status",
      "operator": "eq",
      "value": "active"
    },
    {
      "attribute": "is_verified",
      "operator": "eq",
      "value": true
    }
  ],
  "logical_operator": "and",
  "relations": [
    {
      "relation_name": "profile",
      "load_strategy": "select",
      "nested_relations": []
    }
  ]
}'
"""
