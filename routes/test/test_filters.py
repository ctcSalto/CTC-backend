from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session
from database.models.test.author import AuthorResponse
from database.services.filter.filters import Filter, QueryBuilderError, extract_filter_fields, EnhancedFieldFilter, filter_model_response
from database.database import Services, get_services, get_session

from utils.logger import show

router = APIRouter(prefix="/test", tags=["Test"])

@router.post("/users", status_code=status.HTTP_200_OK)  # Quité response_model porque ahora filtramos campos
async def get_users(
    filters: Filter = Depends(),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
    #current_user: User = Depends(get_current_active_user)
):
    try:
        show(filters)
        authors = services.authorService.get_with_filters(session, filters)
        
        # DEBUG: Agregar esta línea temporalmente
        from database.services.filter.debug_test import enhanced_debug_endpoint_filtering
        filtered_authors = enhanced_debug_endpoint_filtering(authors, filters)
        
        return filtered_authors
    except QueryBuilderError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))