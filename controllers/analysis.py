from typing import Dict, List, Any, Optional, Tuple
import sec_parser as sp
from datetime import date
import httpx
import logging
from database.mongo_db import get_filing
from fastapi import HTTPException
from pydantic import BaseModel

# Configure logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
HEADERS = {"User-Agent": "YourCompanyName YourAppName (your-email@example.com)"}


# 1. Pydantic models
class Section(BaseModel):
    title: str
    text: str
    start_page: Optional[int]
    end_page: Optional[int]

class Document(BaseModel):
    cik: str
    accession_number: str
    form_type: str
    filing_date: date
    report_period: Optional[str]
    metadata: Dict[str, Any]
    sections: List[Section]

# 2. Metadata extractor base + 10-K example
class BaseMetadataExtractor:
    def __init__(self, elements, tree):
        self.elements = elements
        self.tree = tree

    def extract(self) -> Dict[str, Any]:
        raise NotImplementedError

    # helper stubs
    def _find_heading(self, heading: str) -> str:
        # implement search in self.tree or elements
        return ""

    def _find_date(self, prefix: str) -> date:
        # implement date parsing from text
        return date.today()

class TenKExtractor(BaseMetadataExtractor):
    def extract(self) -> Dict[str, Any]:
        return {
            "company_name": self._find_heading("Item 1. Business"),
            "report_period": self._find_date("For the fiscal year ended"),
            "filing_date": self._find_date("Date of Report"),
        }
class DefaultExtractor(BaseMetadataExtractor):
    def extract(self) -> Dict[str, Any]:
        # fallback: grab first heading and dates heuristically
        first_heading = self.elements[0].text if self.elements else ""
        filing_date = self._find_date("Date")  # best‐effort
        return {
            "title": first_heading,
            "filing_date": filing_date,
            "note": "fallback extractor – key fields may be missing"
        }



# Enhanced controller with document-type awareness and analysis optimization
async def fetch_analysis(cik: str, accession_number: str) -> Dict[str, Any]:
    # Get filing metadata
    filing = await get_filing(cik, accession_number)
    form_type = filing['form_type']
    
    # Fetch document content
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(filing['url'], headers=HEADERS)
        html = resp.content
    
    # Select appropriate parser based on form type
   
    elements: list = sp.Edgar10QParser().parse(html)
    text_elements = [elem.text for elem in elements]
    tree = sp.TreeBuilder().build(elements)
    print("\n\nTREE",tree.print())
    # select extractor
    extractor_map = {
        "10-K": TenKExtractor,
        # "10-Q": TenQExtractor,
        # "8-K": EightKExtractor,
        # "4":  Form4Extractor,
    }
    if form_type not in extractor_map:
        logging.warning(f"No extractor for {form_type}, using DefaultExtractor")

    extractor_cls = extractor_map.get(form_type, DefaultExtractor)
    extractor = extractor_cls(elements, tree)
    metadata  = extractor.extract()
    sections  = build_sections(tree)

    doc = Document(
        cik=cik,
        accession_number=accession_number,
        form_type=form_type,
        filing_date=metadata["filing_date"],
        report_period=metadata.get("report_period").isoformat(),
        metadata=metadata,
        sections=sections,
    )
    
    return doc.model_dump()

def build_sections(tree) -> List[Section]:
    sections = []
    for node in tree:
        body = " ".join(c.text for c in node.get_descendants())
        sections.append(Section(
            title=node.text or "",
            text=body,
            start_page=getattr(node, "start_page", None),
            end_page=getattr(node, "end_page", None),
        ))
    return sections

