from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..core.config import get_config
from ..db.models import EngineerORM, EngineerTokenORM
from ..db.session import get_db, session_scope


def _hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def ensure_admin(self, username: str, password: str) -> EngineerORM:
        hashed = _hash_password(password)
        stmt = select(EngineerORM).where(EngineerORM.username == username)
        engineer = self._db.scalars(stmt).first()
        if engineer:
            if engineer.password_hash != hashed:
                engineer.password_hash = hashed
                self._db.add(engineer)
                self._db.commit()
            if engineer.role != "admin":
                engineer.role = "admin"
                self._db.add(engineer)
                self._db.commit()
            return engineer

        engineer = EngineerORM(
            username=username,
            password_hash=hashed,
            role="admin",
        )
        self._db.add(engineer)
        self._db.commit()
        self._db.refresh(engineer)
        return engineer

    def authenticate(self, username: str, password: str) -> Optional[EngineerORM]:
        hashed = _hash_password(password)
        stmt = select(EngineerORM).where(EngineerORM.username == username)
        engineer = self._db.scalars(stmt).first()
        if not engineer:
            return None
        if engineer.password_hash != hashed:
            return None
        return engineer

    def issue_token(self, engineer: EngineerORM) -> str:
        self._db.execute(
            delete(EngineerTokenORM).where(EngineerTokenORM.engineer_id == engineer.id)
        )
        token_value = secrets.token_urlsafe(32)
        token = EngineerTokenORM(token=token_value, engineer_id=engineer.id)
        self._db.add(token)
        self._db.commit()
        return token_value

    def revoke_token(self, token_value: str) -> None:
        self._db.execute(delete(EngineerTokenORM).where(EngineerTokenORM.token == token_value))
        self._db.commit()

    def get_engineer_by_token(self, token_value: str) -> Optional[EngineerORM]:
        stmt = (
            select(EngineerTokenORM)
            .options(selectinload(EngineerTokenORM.engineer))
            .where(EngineerTokenORM.token == token_value)
        )
        token = self._db.scalars(stmt).first()
        if not token:
            return None
        return token.engineer


_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_bearer_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> HTTPAuthorizationCredentials:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return credentials


def get_current_engineer(
    credentials: HTTPAuthorizationCredentials = Depends(get_bearer_credentials),
    auth_service: AuthService = Depends(get_auth_service),
) -> EngineerORM:
    engineer = auth_service.get_engineer_by_token(credentials.credentials)
    if engineer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return engineer


def require_admin(engineer: EngineerORM = Depends(get_current_engineer)) -> EngineerORM:
    if engineer.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
    return engineer


def ensure_initial_admin() -> None:
    config = get_config()
    with session_scope() as db:
        service = AuthService(db)
        service.ensure_admin(config.initial_admin_username, config.initial_admin_password)
