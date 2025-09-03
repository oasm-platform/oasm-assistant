from enum import Enum as PyEnum


class RoleEnum(str, PyEnum):
    USER = "user"
    ADMIN = "admin"