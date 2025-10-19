import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(user_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_phone(*, session: Session, phone: str) -> User | None:
    statement = select(User).where(User.phone == phone)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, phone: str, verification_code: str) -> User | None:
    db_user = get_user_by_phone(session=session, phone=phone)
    if not db_user:
        return None
    # 这里需要根据实际的验证码验证逻辑来实现
    # 暂时返回用户，实际应该验证验证码
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item
