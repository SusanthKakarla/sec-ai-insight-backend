from typing import Dict, List, Any, Optional, Tuple
import sec_parser as sp
from datetime import date
import httpx
import logging
from database.mongo_db import get_filing
from fastapi import HTTPException
from pydantic import BaseModel
import re
from bs4 import BeautifulSoup, Tag
from collections import OrderedDict
import tiktoken
from .document_analyzer import analyze_document_content
import groq
import os
from dotenv import load_dotenv

# Configure logging
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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

class DocumentAnalysis(BaseModel):
    cik: str
    text_elements: List[str]
    sections: Dict[str, List[str]]
    groq_analysis: Optional[List[str]] = None
    form_type: str

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

def split_into_token_chunks(text: str, max_tokens: int = 1000, model: str = "gpt-3.5-turbo") -> list[str]:
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    return [
        enc.decode(tokens[i : i + max_tokens])
        for i in range(0, len(tokens), max_tokens)
    ]


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

    section_config = {
        "10-K": ["Item 1.", "Item 1A.","Item 1B.","Item 1C.","Item 2.","Item 3.","Item 4.", "Item 5.","Item 6.","Item 7.","Item 7A.","Item 8.", "Item 9.", "Item 9A.", "Item 9B.", "Item 9C.", "Item 10.", "Item 11.", "Item 12.", "Item 13.", "Item 14.", "Item 15.", "Item 16.", "Item 153."],
        "10-Q": ["Filed Status", "Incorporation by Reference"],
        "8-K": "all",  # Example of a document type that should be parsed by token size
        "default": "all"  # Default case for undefined form types
    }
    
    tree = sp.TreeBuilder().build(elements)
    nodes_list = list(tree.nodes)

    # Get the appropriate section configuration for the form type
    section_definition = section_config.get(form_type, section_config["default"])

    # Check if the section definition is "all"
    if section_definition == "all":
        # Parse entire document by token size
        sections = {"content": split_into_token_chunks(clean_content(text_elements))}
    else:
        # Parse specific sections
        sections = parse_sec_document(html, section_definition)

    # Perform analysis based on document type
    analysis = analyze_document_content(form_type, sections)

    return DocumentAnalysis(
        cik=cik, 
        text_elements=text_elements, 
        sections=sections, 
        groq_analysis=analysis,
        form_type=form_type
    )

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


def parse_sec_document(html: str, sections_to_extract: list[str], max_tokens: int = 1000) -> OrderedDict[str, list[str]]:
    soup = BeautifulSoup(html, 'html.parser')

    # 1) prepare ordered raw-text store
    raw_texts = OrderedDict((sec, "") for sec in sections_to_extract)

    # 2) compile exact-match patterns
    patterns = {
        sec: re.compile(rf'^\s*{re.escape(sec)}(?=\s|$)', re.IGNORECASE)
        for sec in sections_to_extract
    }

    current = None
    buffer = []

    for elem in soup.find_all(string=True):
        if not isinstance(elem.parent, Tag):
            continue
        text = elem.get_text(strip=True)
        # detect header
        hit = next((sec for sec, pat in patterns.items() if pat.match(text)), None)
        if hit:
            if current:
                raw_texts[current] = clean_content(buffer)
                buffer = []
            current = hit
            buffer.append(text)
            for sib in elem.parent.next_siblings:
                if isinstance(sib, Tag) and any(p.match(sib.get_text(strip=True)) for p in patterns.values()):
                    break
                if isinstance(sib, Tag):
                    buffer.append(sib.get_text(strip=True))
        elif current:
            buffer.append(text)

    # save last
    if current and buffer:
        raw_texts[current] = clean_content(buffer)

    # 3) split into token chunks & wrap missing
    result = OrderedDict()
    for sec, txt in raw_texts.items():
        if not txt:
            result[sec] = ["not found"]
        else:
            chunks = split_into_token_chunks(txt, max_tokens)
            result[sec] = chunks
    return result

def clean_content(content_list: list) -> str:
    """Clean and normalize extracted content"""
    full_text = ' '.join(content_list)
    # Remove excessive whitespace and line breaks
    return re.sub(r'\s+', ' ', full_text).strip()