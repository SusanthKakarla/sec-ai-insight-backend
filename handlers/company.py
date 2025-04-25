from fastapi import APIRouter, Path, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

router = APIRouter()

class Filing(BaseModel):
    _id: str
    formType: str
    baseForm: str
    isAmendment: bool
    amendedAccession: Optional[str] = None
    filingDate: str
    url: HttpUrl

class CompanyResponse(BaseModel):
    cik: str
    name: str
    ticker: str
    filings: List[Filing]
    currentPage: int
    totalPages: int
    totalFilings: int
    filingType: str
    allFilingTypes: List[str]

@router.get("/api/companies/{cik}", response_model=CompanyResponse)
async def get_company(
    cik: str = Path(..., description="CIK of the company"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    filing_type: str = Query("", description="Filter by filing type")
) -> CompanyResponse:
    """
    Get detailed company info and filings by CIK.
    Supports pagination and filtering by filing type.
    """
    from controllers.company import get_company as get_company_controller
    
    try:
        return await get_company_controller(cik, page, limit, filing_type)
    except HTTPException as e:
        raise e 