import base64
from uuid import UUID


def encode_cursor(uuid: UUID) -> str:
    return base64.urlsafe_b64encode(str(uuid).encode()).decode()


def decode_cursor(cursor: str) -> UUID:
    return UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
