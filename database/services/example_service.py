from sqlmodel import Session, select
from ..models.example import Example, ExampleCreate, ExampleRead, ExampleUpdate
from typing import List
from sqlalchemy.exc import IntegrityError, NoResultFound

class ExampleService:

    def create_example(self, example: ExampleCreate, session: Session) -> Example:
        with session:
            new_example = Example(**example.model_dump())
            session.add(new_example)
            session.commit()
            session.refresh(new_example)
            return new_example

    def get_examples(self, session: Session, offset: int = 0, limit: int = 10) -> List[Example]:
        with session:
            statement = select(Example).offset(offset).limit(limit)
            examples = session.exec(statement).all()
            if not examples:
                return []
            return examples

    def get_example_by_id(self, id: int, session: Session) -> Example:
        with session:
            statement = select(Example).where(Example.id == id)
            example = session.exec(statement).one()
            if not example:
                return None
            return example

    def update_example(self, id: int, example_update: ExampleUpdate, session: Session) -> Example:
        with session:
            statement = select(Example).where(Example.id == id)
            old_example = session.exec(statement).one()
            
            update_data = example_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_example, key, value)
                
            session.commit()
            session.refresh(old_example)
            return old_example

    def delete_example(self, id: int, session: Session) -> bool:
        with session:
            statement = select(Example).where(Example.id == id)
            example = session.exec(statement).one()
            session.delete(example)
            session.commit()
            return True