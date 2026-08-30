from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


class DuplicateUserError(Exception):
    """用户名或邮箱违反数据库唯一约束。"""


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self._session.scalar(statement)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self._session.scalar(statement)

    def get_by_identifier(self, identifier: str) -> User | None:
        statement = select(User).where(
            or_(User.username == identifier, User.email == identifier.lower())
        )
        return self._session.scalar(statement)

    def create(self, user: User) -> User:
        self._session.add(user)
        try:
            self._session.commit()
            self._session.refresh(user)
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateUserError from exc
        return user
