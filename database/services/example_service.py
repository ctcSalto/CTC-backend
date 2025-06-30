from sqlmodel import Session, select
from ..models.example import Example, ExampleCreate, ExampleRead, ExampleUpdate
from typing import List
from sqlalchemy.exc import IntegrityError, NoResultFound

from database.services.filter.filters import BaseServiceWithFilters

class ExampleService(BaseServiceWithFilters[Example]):
    def __init__(self):
        super().__init__(Example)

    def create_example(self, example: ExampleCreate, session: Session) -> ExampleRead:
        with session:
            new_example = Example(**example.model_dump())
            session.add(new_example)
            session.commit()
            session.refresh(new_example)
            return ExampleRead.from_orm(new_example)

    def get_examples(self, session: Session, offset: int = 0, limit: int = 10) -> List[ExampleRead]:
        with session:
            statement = select(Example).offset(offset).limit(limit)
            examples = session.exec(statement).all()
            if not examples:
                return []
            return [ExampleRead.from_orm(example) for example in examples]

    def get_example_by_id(self, id: int, session: Session) -> ExampleRead:
        with session:
            statement = select(Example).where(Example.id == id)
            example = session.exec(statement).one()
            if not example:
                return None
            return ExampleRead.from_orm(example)

    def update_example(self, id: int, example_update: ExampleUpdate, session: Session) -> ExampleRead:
        with session:
            statement = select(Example).where(Example.id == id)
            old_example = session.exec(statement).one()
            
            update_data = example_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_example, key, value)
                
            session.commit()
            session.refresh(old_example)
            return ExampleRead.from_orm(old_example)

    def delete_example(self, id: int, session: Session) -> bool:
        with session:
            statement = select(Example).where(Example.id == id)
            example = session.exec(statement).one()
            session.delete(example)
            session.commit()
            return True