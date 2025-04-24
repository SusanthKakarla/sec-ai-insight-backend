from fastapi import APIRouter, Query
from typing import List
from pydantic import BaseModel

router = APIRouter()

class CompanyResponse(BaseModel):
    cik: str
    name: str
    ticker: str

@router.get("/api/companies/search", response_model=List[CompanyResponse])
async def search_companies(
    query: str = Query(..., min_length=1, description="Search query for company name or ticker")
) -> List[CompanyResponse]:
    """
    Search for companies by name or ticker.
    Supports partial matching and returns up to 10 results.
    """
    from controllers.search import search_companies as search_controller
    
    # Strip whitespace and validate query
    query = query.strip()
    if not query:
        return []
    
    # Call the controller to handle the search logic
    return await search_controller(query)
