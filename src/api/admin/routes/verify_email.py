from fastapi import APIRouter, HTTPException, Depends, Query
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(prefix="/verify-email", tags=["Verify Email"])


