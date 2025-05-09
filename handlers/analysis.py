
from fastapi import APIRouter, Request, Path
from pydantic import BaseModel, HttpUrl
from typing import List

router = APIRouter()

class SectionAnalysis(BaseModel):
    section_name: str
    analysis: str

# class AnalysisResponse(BaseModel):
#     cik: str
#     accession_number: str
#     summary: str
#     section_analysis: List[SectionAnalysis]

@router.get("/api/analysis/{cik}/{accession_number}")
async def analysis(
    cik: str = Path(..., description="CIK of the company"),
    accession_number: str = Path(..., description="Accession number of the filing")
):
    from controllers.analysis import fetch_analysis
    result = await fetch_analysis(cik, accession_number)
    return result