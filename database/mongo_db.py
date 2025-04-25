import logging 
import requests
import os 
from dotenv import load_dotenv
from pymongo import MongoClient
from fastapi import HTTPException
import re
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any
from datetime import datetime, timedelta

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logging.error("MONGO_URI is not set in environment variables.")
    raise ValueError("MONGO_URI environment variable is not set.")

client = MongoClient(MONGO_URI)
async_client = AsyncIOMotorClient(MONGO_URI)
db = client.companies  # Replace with your database name
companies_collection = db.filings  # Replace with your collection name
async_companies_collection = async_client.companies.filings

# SEC EDGAR API settings
BASE_URL = "https://data.sec.gov/submissions"
HEADERS = {"User-Agent": "sec-ai-insight-backend"}
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"


async def setup_search_indexes():
    """Create necessary indexes for efficient company searching"""
    await async_companies_collection.create_index([("name", "text"), ("ticker", "text")])
    await async_companies_collection.create_index("name")
    await async_companies_collection.create_index("ticker")

async def search_companies_by_ticker(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search companies by ticker prefix"""
    pattern = re.compile(f"^{re.escape(query)}", re.IGNORECASE)
    return await async_companies_collection.find(
        {"ticker": pattern},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0}
    ).limit(limit).to_list(limit)

async def search_companies_by_name(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search companies by name prefix"""
    pattern = re.compile(f"^{re.escape(query)}", re.IGNORECASE)
    return await async_companies_collection.find(
        {"name": pattern},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0}
    ).limit(limit).to_list(limit)

async def search_companies_by_text(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Full text search across company fields"""
    return await async_companies_collection.find(
        {"$text": {"$search": query}},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0, "score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]).limit(limit).to_list(limit)

async def get_filing(cik: str, accession_number: str):
    logging.info(f"Received request for CIK {cik} and accession number {accession_number}")
    try: 
        logging.info(f"Querying MongoDB for CIK {cik} and accession number {accession_number}")
        company = companies_collection.find_one(
            {"cik": cik.lstrip('0')},
            {"filings": {"$elemMatch": {"_id": accession_number}}}
        )

        if not company or not company.get('filings'):
            logging.warning(f"No filing found for CIK {cik} and accession number {accession_number}")
            raise HTTPException(
                status_code=404,
                detail=f"No filing found for CIK {cik} and accession number {accession_number}"
            )
        return {
            "cik": cik, 
            "accessionNumber": accession_number, 
            "url": company['filings'][0]['url'], 
            "form_type": company['filings'][0]['formType']
        }
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch document: {e}")

async def get_company_by_cik(cik: str):
    """Get the company document for the given CIK number, including filings."""
    stripped_cik = cik.lstrip('0')
    company = await async_companies_collection.find_one(
        {"cik": stripped_cik},
        {"_id": 1, "cik": 1, "name": 1, "ticker": 1, "filings": 1}
    )
    if not company:
        logging.warning(f"Company with CIK {cik} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Company with CIK {cik} not found."
        )

    # Check if we need to fetch new filings
    today = datetime.now()
    five_years_ago = today - timedelta(days=5*365)
    
    # Find the latest filing date in our database
    filings = company.get("filings", [])
    latest_filing_date = max([datetime.strptime(f.get("filingDate", "1970-01-01"), "%Y-%m-%d") 
                            for f in filings]) if filings else datetime.min
    
    # If latest filing is older than today, check for updates
    if today > latest_filing_date:
        print("\n\n\nFetching new filings from SEC for CIK", cik, "\n\n\n")
        logging.info(f"Fetching new filings from SEC for CIK {cik}")
        await update_company_filings(cik)
        
        # Fetch the updated company document
        company = await async_companies_collection.find_one(
            {"cik": stripped_cik},
            {"_id": 0, "cik": 1, "name": 1, "ticker": 1, "filings": 1}
        )
    else:
        print("\n\n\nNo new filings found for CIK", cik, "\n\n\n")
        logging.info(f"No new filings found for CIK {cik}")
    
    return company

def fetch_filings(cik: str) -> Dict[str, Any]:
    """Fetches filings data from SEC API"""
    cik_padded = cik.zfill(10)
    cik_value = f"CIK{cik_padded}"
    url = f"{BASE_URL}/{cik_value}.json"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        # Return the recent filings data directly
        return data.get("filings", {}).get("recent", {})
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch filings for CIK {cik}: {str(e)}")
        return {}

def process_filings(cik: str, sec_data: Dict) -> List[Dict]:
    """
    Process SEC filings data into our model format.
    Expects sec_data to be the 'recent' section of the SEC response.
    """
    filings = []
    cutoff_date = datetime.now() - timedelta(days=5*365)
    
    # Get all the arrays from the SEC data
    form_types = sec_data.get('form', [])
    accession_numbers = sec_data.get('accessionNumber', [])
    filing_dates = sec_data.get('filingDate', [])
    primary_docs = sec_data.get('primaryDocument', [])
    
    # Process each filing
    for i in range(len(form_types)):
        try:
            # Skip if we don't have all required fields
            if not all([
                i < len(accession_numbers),
                i < len(filing_dates),
                i < len(primary_docs)
            ]):
                continue
                
            filing_date = datetime.strptime(filing_dates[i], "%Y-%m-%d")
            
            # Skip filings older than 5 years
            if filing_date < cutoff_date:
                continue
                
            # Skip if no primary document
            if not primary_docs[i] or primary_docs[i] in ['xslFormFiling.xml', 'primary_en.xml']:
                continue
                
            # Create filing object matching our model
            filing = {
                "_id": accession_numbers[i],
                "formType": form_types[i],  # Using formType instead of type to match existing model
                "filingDate": filing_dates[i],
                "url": construct_filing_url(cik, accession_numbers[i], primary_docs[i]),
                "isAmendment": form_types[i].endswith('/A'),
                "baseForm": form_types[i].split('/')[0] if form_types[i].endswith('/A') else form_types[i],
                "amendedAccession": accession_numbers[i].replace('-A', '') if form_types[i].endswith('/A') else None
            }
            filings.append(filing)
            
        except (IndexError, KeyError, ValueError) as e:
            logging.error(f"Error processing filing index {i}: {str(e)}")
            continue
    
    # Sort by filing date, newest first
    filings.sort(key=lambda x: x["filingDate"], reverse=True)
    return filings

async def update_company_filings(cik: str):
    """Fetch latest filings from SEC API, merge with existing and update DB"""
    new_filings_data = fetch_filings(cik)
    if not new_filings_data:
        return
        
    structured_filings = process_filings(cik, new_filings_data)
    if not structured_filings:
        return
        
    stripped_cik = cik.lstrip('0')
    company = companies_collection.find_one({"cik": stripped_cik})
    if not company:
        return
        
    existing_filings = company.get("filings", [])
    existing_ids = {x.get("_id") for x in existing_filings}
    
    # Filter out filings we already have
    filings_to_add = [f for f in structured_filings if f["_id"] not in existing_ids]
    
    if filings_to_add:
        # Add new filings to the beginning
        updated_filings = filings_to_add + existing_filings
        # Sort all filings by date
        updated_filings.sort(key=lambda x: x["filingDate"], reverse=True)
        
        # Update the database
        await async_companies_collection.update_one(
            {"cik": stripped_cik},
            {"$set": {"filings": updated_filings}}
        )

def construct_filing_url(cik: str, accession_number: str, primary_doc: str) -> str:
    """Constructs the full EDGAR URL for a filing"""
    formatted_cik = cik.lstrip('0').zfill(10)
    formatted_accession = accession_number.replace("-", "")
    return f"{EDGAR_ARCHIVES_URL}/{formatted_cik}/{formatted_accession}/{primary_doc}"