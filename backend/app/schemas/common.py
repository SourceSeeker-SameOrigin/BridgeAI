from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 500, message: str = "error", data: Any = None) -> "ApiResponse":
        return cls(code=code, message=message, data=data)


class PageRequest(BaseModel):
    page: int = 1
    size: int = 20


class PageResponse(BaseModel, Generic[T]):
    items: List[T] = []
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0
