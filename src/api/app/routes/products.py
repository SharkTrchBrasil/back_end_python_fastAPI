

from fastapi import APIRouter, Form, Depends, HTTPException, UploadFile, File

from src.api.shared_schemas.product import ProductOut

from src.core.dependencies import GetPublicProductDep  # <<< NOVA IMPORTAÇÃO CRUCIAL

router = APIRouter(prefix="/products", tags=["Products"])



@router.get("/{store_url}/{product_id}", response_model=ProductOut)
def get_public_product_details(

        product: GetPublicProductDep,


):

    return product

