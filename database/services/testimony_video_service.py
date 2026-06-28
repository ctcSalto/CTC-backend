from sqlmodel import Session, select
from typing import List, Optional

from ..models.testimony_video import TestimonyVideo, TestimonyVideoCreate, TestimonyVideoRead, TestimonyVideoUpdate


class TestimonyVideoService:
    def add_video(self, testimony_id: int, video: TestimonyVideoCreate, session: Session) -> TestimonyVideoRead:
        """Agregar un video a un testimonio"""
        with session:
            new_video = TestimonyVideo(testimonyId=testimony_id, **video.model_dump())
            session.add(new_video)
            session.commit()
            session.refresh(new_video)
            return TestimonyVideoRead.model_validate(new_video)

    def get_videos_by_testimony(self, testimony_id: int, session: Session) -> List[TestimonyVideoRead]:
        """Obtener los videos de un testimonio ordenados por 'order'"""
        with session:
            statement = (
                select(TestimonyVideo)
                .where(TestimonyVideo.testimonyId == testimony_id)
                .order_by(TestimonyVideo.order)
            )
            videos = session.exec(statement).all()
            return [TestimonyVideoRead.model_validate(video) for video in videos]

    def update_video(self, video_id: int, video_update: TestimonyVideoUpdate, session: Session) -> Optional[TestimonyVideoRead]:
        """Actualizar un video existente"""
        with session:
            statement = select(TestimonyVideo).where(TestimonyVideo.testimonyVideoId == video_id)
            video = session.exec(statement).first()
            if not video:
                return None

            update_data = video_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(video, key, value)

            session.commit()
            session.refresh(video)
            return TestimonyVideoRead.model_validate(video)

    def delete_video(self, video_id: int, session: Session) -> bool:
        """Eliminar un video"""
        with session:
            statement = select(TestimonyVideo).where(TestimonyVideo.testimonyVideoId == video_id)
            video = session.exec(statement).first()
            if not video:
                return False
            session.delete(video)
            session.commit()
            return True
