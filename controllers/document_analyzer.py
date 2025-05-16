from typing import Dict, List, Any
import groq
import os
from dotenv import load_dotenv
from .prompts import get_system_prompt, get_section_prompt
from .rate_limiter import RateLimiter

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize rate limiter
rate_limiter = RateLimiter(
    tokens_per_minute=6000,  # Adjust based on your Groq tier
    max_tokens_per_request=4000,  # Conservative limit to avoid errors
    model="llama3-8b-8192"
)

def analyze_document_content(form_type: str, sections: Dict[str, List[str]], max_tokens: int = 8000) -> List[str]:
    """
    Analyze document content using Groq, with different strategies based on document type and size.
    
    Args:
        form_type: Type of SEC document (e.g., "10-K", "8-K")
        sections: Dictionary of sections and their content chunks
        max_tokens: Maximum tokens for Groq model (llama3-8b-8192 has 8192 context window)
    
    Returns:
        List[str]: List of analysis responses
    """
    if form_type == "10-K":
        return analyze_10k(sections)
    elif form_type == "10-Q":
        return analyze_10q(sections)
    else:
        # For smaller documents or undefined types, analyze the entire content
        return analyze_simple_document(sections, form_type)

def analyze_10k(sections: Dict[str, List[str]]) -> List[str]:
    """
    Specialized analysis for 10-K documents, which are typically large and structured.
    """
    # Group related sections for analysis
    section_groups = {
        "business_overview": ["Item 1.", "Item 1A.", "Item 1B.", "Item 1C."],
        "financial_metrics": ["Item 6.", "Item 7.", "Item 7A."],
        "risk_factors": ["Item 1A."],
        "management_discussion": ["Item 7."],
    }
    
    analyses = []
    
    # Analyze each group of related sections
    for group_name, section_keys in section_groups.items():
        group_content = []
        for key in section_keys:
            if key in sections:
                group_content.extend(sections[key])
        
        if group_content:
            # Combine content chunks and analyze
            combined_content = " ".join(group_content)
            # Split content into manageable chunks
            chunks = rate_limiter.split_text_into_chunks(combined_content)
            chunk_analyses = []
            
            for chunk in chunks:
                # Wait if necessary to respect rate limits
                rate_limiter.wait_if_needed(rate_limiter.count_tokens(chunk))
                
                analysis = groq_analysis(
                    chunk,
                    system_prompt=get_section_prompt("10-K", group_name)
                )
                chunk_analyses.append(analysis)
            
            # Add section header and analyses to the list
            analyses.append(f"{group_name.upper()} ANALYSIS:")
            analyses.extend(chunk_analyses)
            analyses.append("")  # Add empty line between sections
    
    return analyses

def analyze_10q(sections: Dict[str, List[str]]) -> List[str]:
    """
    Specialized analysis for 10-Q documents.
    """
    # Similar to 10-K but with different section groupings
    section_groups = {
        "financial_statements": ["Item 1.", "Item 2."],
        "management_discussion": ["Item 2."],
    }
    
    analyses = []
    for group_name, section_keys in section_groups.items():
        group_content = []
        for key in section_keys:
            if key in sections:
                group_content.extend(sections[key])
        
        if group_content:
            combined_content = " ".join(group_content)
            # Split content into manageable chunks
            chunks = rate_limiter.split_text_into_chunks(combined_content)
            chunk_analyses = []
            
            for chunk in chunks:
                # Wait if necessary to respect rate limits
                rate_limiter.wait_if_needed(rate_limiter.count_tokens(chunk))
                
                analysis = groq_analysis(
                    chunk,
                    system_prompt=get_section_prompt("10-Q", group_name)
                )
                chunk_analyses.append(analysis)
            
            # Add section header and analyses to the list
            analyses.append(f"{group_name.upper()} ANALYSIS:")
            analyses.extend(chunk_analyses)
            analyses.append("")  # Add empty line between sections
    
    return analyses

def analyze_simple_document(sections: Dict[str, List[str]], form_type: str) -> List[str]:
    """
    Analyze smaller documents or those without specific section requirements.
    """
    if "content" in sections:
        # For documents parsed by token size
        content = " ".join(sections["content"])
    else:
        # For documents with sections but no specific analysis requirements
        content = " ".join(
            chunk for section in sections.values() for chunk in section
        )
    
    # Split content into manageable chunks
    chunks = rate_limiter.split_text_into_chunks(content)
    analyses = []
    
    for chunk in chunks:
        # Wait if necessary to respect rate limits
        rate_limiter.wait_if_needed(rate_limiter.count_tokens(chunk))
        
        analysis = groq_analysis(
            chunk,
            system_prompt=get_system_prompt(form_type)
        )
        analyses.append(analysis)
    
    return analyses

def groq_analysis(text: str, system_prompt: str) -> str:
    """
    Perform analysis using Groq API with rate limiting.
    """
    client = groq.Groq(api_key=GROQ_API_KEY)
    
    # Calculate total tokens for the request
    total_tokens = rate_limiter.count_tokens(text) + rate_limiter.count_tokens(system_prompt)
    
    # Record token usage
    rate_limiter.record_token_usage(total_tokens)
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content 