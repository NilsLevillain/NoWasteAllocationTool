from pydantic import ValidationError
from schemas import AllocationRequest
from typing import Optional, Dict, Any

def parse_and_validate_allocation_request(data: Dict[str, Any]) -> Optional[AllocationRequest]:
    """
    Parses and validates the incoming allocation request data using Pydantic models.

    Args:
        data: A dictionary representing the JSON payload.

    Returns:
        An AllocationRequest object if validation is successful, None otherwise.
        Prints validation errors to stderr if validation fails.
    """
    try:
        request_model = AllocationRequest(**data)
        return request_model
    except ValidationError as e:
        # In a real application, you might log this error or raise a custom exception
        # to be handled by the API framework (e.g., FastAPI) to return a 422 response.
        print(f"Input validation failed:\n{e}")
        return None
