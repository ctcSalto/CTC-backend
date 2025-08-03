from fastapi import APIRouter, HTTPException, status, UploadFile, Form, Depends, File
from database.models.example import ExampleCreate, ExampleRead, ExampleUpdate, Example
from database.database import Services, get_services, get_session
from typing import List
import json
from sqlmodel import Session, select

from database.services.filter.filters import Filter

from database.services.auth.dependencies import get_current_active_user, require_admin_role
from database.models.user import UserRead

from utils.logger import show

from exceptions import AppException
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

def handle_app_exception(e):
    if isinstance(e, IntegrityError):
        # Podés incluso analizar `str(e)` para saber más detalles
        raise HTTPException(status_code=400, detail="Violación de restricción de unicidad")
    # Podés manejar otros tipos también
    raise HTTPException(status_code=500, detail="Error interno del servidor")


router = APIRouter(prefix="/example", tags=["Example"])

# current_user: UsuarioRead = Depends(get_current_active_user) para usuarios autenticados
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
    name: str,
    email: str,
    age: int,
    image: UploadFile = File(...),
    images: List[UploadFile] = File(...),
    services: Services = Depends(get_services), 
    #current_user: UsuarioRead = Depends(require_admin_role),
    session: Session = Depends(get_session)
) -> ExampleRead:
    try:
        show(images)
        image_url = None
        if image:
            image_url = await services.supabaseService.upload_image(image, folder=f"images")

        image_urls = None
        if images:
            image_urls = await services.supabaseService.upload_multiple_images(images, folder=f"images")

        show(image_url)
        show(image_urls)

        example = ExampleCreate(name=name, email=email, age=age, image_url=image_url, image_urls=image_urls)
        show(example)
        new_example = services.exampleService.create_example(example, session)
        show(new_example)
        return new_example
    except Exception as e:
        raise handle_app_exception(e)

@router.put("/updateExample/{id}", response_model=ExampleRead, tags=["Example"])
async def update_example(
    id: int, 
    name: str,
    email: str,
    age: int,
    image: UploadFile = File(...),
    images: List[UploadFile] = File(...),
    services: Services = Depends(get_services), 
    #current_user: UserRead = Depends(require_admin_role),
    session: Session = Depends(get_session)
    ) -> ExampleRead:
    try:
        image_url = None
        if image:
            image_url = await services.supabaseService.upload_image(image, folder=f"images")

        image_urls = None
        if images:
            image_urls = await services.supabaseService.upload_multiple_images(images, folder=f"images")

        example = ExampleUpdate(name=name, email=email, age=age, image_url=image_url, image_urls=image_urls)
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
        example: Example = services.exampleService.get_example_by_id(id, session)

        # Validar que el ejemplo existe
        if not example:
            raise HTTPException(status_code=404, detail="Example not found")

        # Validar que el ejemplo tiene una imagenes y borrarlas
        if example.image_url:
            services.supabaseService.delete_image(example.image_url)

        if example.image_urls:
            services.supabaseService.delete_image(example.image_urls)

        services.exampleService.delete_example(id, session)
        return {"message": "Example deleted successfully"}
    except Exception as e:
        raise handle_app_exception(e)


# -------------------------------------------------------------------------------------------------------
# Endpoint actualizado
@router.post("/getExamplesWithFilters", response_model=List[ExampleRead], tags=["Example"])
async def get_examples(
    filters: Filter,
    services: Services = Depends(get_services),
    current_user: UserRead = Depends(get_current_active_user),
    session: Session = Depends(get_session)
) -> List[ExampleRead]:
    try:
        examples = services.exampleService.get_with_filters(session, filters)
        return examples
    except Exception as e:
        raise handle_app_exception(e)

# Ejemplo de request JSON:
"""
{
    "conditions": [
        {
            "attribute": "name",
            "operator": "contains",
            "value": "test"
        },
        {
            "attribute": "user.email",
            "operator": "eq",
            "value": "user@example.com"
        },
        {
            "attribute": "user.profile.age",
            "operator": "gte",
            "value": 18
        }
    ],
    "relations": [
        {
            "relation_name": "user",
            "load_strategy": "select",
            "nested_relations": [
                {
                    "relation_name": "profile",
                    "load_strategy": "joined"
                }
            ]
        },
        {
            "relation_name": "category",
            "load_strategy": "joined"
        }
    ],
    "limit": 20,
    "offset": 0,
    "order_by": "user.profile.created_at",
    "order_direction": "desc"
}
"""
# -------------------------------------------------------------------------------------------------------
