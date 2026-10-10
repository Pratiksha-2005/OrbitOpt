"""Custom exception types and error structures for OrbitOpt."""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status


class OrbitOptException(Exception):
    """Base exception class for OrbitOpt application errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[List[Dict[str, Any]]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or []
        self.status_code = status_code


class ResourceNotFoundError(OrbitOptException):
    """Raised when a requested resource (Dataset, Schedule Run) does not exist."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            message=f"{resource} with ID '{resource_id}' was not found.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class DatasetValidationError(OrbitOptException):
    """Raised when a dataset fails consistency or feasibility validation."""

    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(
            message=message,
            error_code="DATASET_VALIDATION_ERROR",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class SchedulingEngineError(OrbitOptException):
    """Raised when the scheduling engine encounters an unrecoverable failure."""

    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(
            message=message,
            error_code="SCHEDULING_ENGINE_ERROR",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class InvalidOutageError(OrbitOptException):
    """Raised when an outage interval or station configuration is invalid."""

    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(
            message=message,
            error_code="INVALID_OUTAGE_INTERVAL",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
