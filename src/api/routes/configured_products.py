from fastapi import APIRouter, Depends

from src.api.dependencies import get_configured_product_service
from src.models.configured_product import (
    ConfiguredProductRequest,
    ConfiguredProductResponse,
)
from src.services.configured_product_service import ConfiguredProductService

router = APIRouter(
    prefix="/api/v1/configured-products",
    tags=["Configured Products"],
)

@router.post("/get-or-create", response_model=ConfiguredProductResponse)
def get_or_create(
    request: ConfiguredProductRequest,
    service: ConfiguredProductService = Depends(get_configured_product_service),
) -> ConfiguredProductResponse:
    return service.get_or_create(request)
