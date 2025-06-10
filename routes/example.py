from fastapi import APIRouter, HTTPException, status, Depends
from database.models.example import ExampleCreate, ExampleRead, ExampleUpdate
from database.database import Services, get_services, get_session
from typing import List
from sqlmodel import Session

from database.services.auth.dependencies import get_current_active_user, require_admin_role
from database.models.user import UserRead


from exceptions import AppException
def handle_app_exception(e: AppException):
    raise HTTPException(status_code=e.status_code, detail=e.message)

router = APIRouter(prefix="/example", tags=["Example"])

# current_user: UserRead = Depends(get_current_active_user) para usuarios autenticados
# require_admin_role para usuarios con rol de administrador
@router.get("/getExampleById/{id}", response_model=ExampleRead)
async def get_example_by_id(
    id: int,
    services: Services = Depends(get_services),
    current_user: UserRead = Depends(get_current_active_user),
    session: Session = Depends(get_session)
) -> ExampleRead:
    try:
        example = services.exampleService.get_example_by_id(id, session)
        return example
    except Exception as e:
        raise handle_app_exception(e)

@router.get("/getExamples", response_model=List[ExampleRead], tags=["Example"])
async def get_examples(
    services: Services = Depends(get_services), 
    offset: int = 0, 
    limit: int = 10, 
    current_user: UserRead = Depends(get_current_active_user),
    session: Session = Depends(get_session)
) -> List[ExampleRead]:
    try:
        examples = services.exampleService.get_examples(session, offset, limit)
        return examples
    except Exception as e:
        raise handle_app_exception(e)

@router.post("/createExample", response_model=ExampleRead, tags=["Example"], status_code=status.HTTP_201_CREATED)
async def create_example(
    example: ExampleCreate, 
    services: Services = Depends(get_services), 
    current_user: UserRead = Depends(require_admin_role),
    session: Session = Depends(get_session)
) -> ExampleRead:
    try:
        new_example = services.exampleService.create_example(example, session)
        return new_example
    except Exception as e:
        raise handle_app_exception(e)

@router.put("/updateExample/{id}", response_model=ExampleRead, tags=["Example"])
async def update_example(
    id: int, 
    example: ExampleUpdate, services: Services = Depends(get_services), 
    current_user: UserRead = Depends(require_admin_role),
    session: Session = Depends(get_session)
    ) -> ExampleRead:
    try:
        updated_example = services.exampleService.update_example(id, example, session)
        return updated_example
    except Exception as e:
        raise handle_app_exception(e)

@router.delete("/deleteExample/{id}", tags=["Example"])
async def delete_example(
    id: int, 
    services: Services = Depends(get_services), 
    session: Session = Depends(get_session),
    current_user: UserRead = Depends(require_admin_role)) -> dict:
    try:
        services.exampleService.delete_example(id, session)
        return {"message": "Example deleted successfully"}
    except Exception as e:
        raise handle_app_exception(e)


