from typing import List, Dict, Any
from database.mongo_db import (
    search_companies_by_ticker,
    search_companies_by_name,
    search_companies_by_text
)

def deduplicate_companies(companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate companies by CIK number while preserving order.
    """
    seen_ciks = set()
    unique_companies = []
    
    for company in companies:
        if company['cik'] not in seen_ciks:
            seen_ciks.add(company['cik'])
            unique_companies.append(company)
    
    return unique_companies

async def search_companies(query: str) -> List[Dict[str, Any]]:
    """
    Search for companies using a tiered approach:
    1. First try exact prefix matching on ticker
    2. Then try prefix matching on company name
    3. Finally fall back to text search for more flexible matching
    
    Results are deduplicated by CIK number.
    """
    # Try ticker search first (most specific)
    companies = await search_companies_by_ticker(query)
    if companies:
        return deduplicate_companies(companies)
    
    # Try name search next
    companies = await search_companies_by_name(query)
    if companies:
        return deduplicate_companies(companies)
    
    # Fall back to text search
    companies = await search_companies_by_text(query)
    return deduplicate_companies(companies)
