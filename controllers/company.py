from typing import Dict, Any, List
from database.mongo_db import get_company_by_cik, update_company_filings
from datetime import datetime
from math import ceil

async def get_company(cik: str, page: int, limit: int, filing_type: str = "") -> Dict[str, Any]:
    """
    Get company and its filings for a given CIK.
    Includes pagination and optional filing type filtering.
    """
    # Get company data (this will also fetch and merge new SEC filings if needed)
    company = await get_company_by_cik(cik)
    
    # Get all filings
    filings = company.get("filings", [])
    
    # Get all unique filing types for metadata
    all_filing_types = ["All"] + list(set(f.get("formType") for f in filings))
    
    # Filter by filing type if specified
    if filing_type and filing_type != "All":
        filings = [f for f in filings if f.get("formType") == filing_type]
    
    # Sort filings by date, latest first
    filings.sort(key=lambda x: x.get("filingDate", ""), reverse=True)
    
    # Calculate pagination
    total_filings = len(filings)
    total_pages = ceil(total_filings / limit)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    # Slice the filings for the requested page
    paginated_filings = filings[start_idx:end_idx]
    
    return {
        "cik": company["cik"],
        "name": company["name"],
        "ticker": company["ticker"],
        "filings": paginated_filings,
        "currentPage": page,
        "totalPages": total_pages,
        "totalFilings": total_filings,
        "filingType": filing_type or "All",
        "allFilingTypes": all_filing_types
    } 