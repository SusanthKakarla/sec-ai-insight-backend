from bs4 import BeautifulSoup, Tag
import re   

def extract_sec_headers(html: str) -> list:
    """
    Extract section headers from an SEC document.
    
    Args:
        html (str): HTML content of the SEC document
        
    Returns:
        list: List of dictionaries containing header information with format:
              [{"text": "header text", "level": level, "page": page_number}, ...]
    """
    soup = BeautifulSoup(html, 'html.parser')
    headers = []
    
    # Pattern to match common SEC document headers
    header_pattern = re.compile(
        r'^\s*(?:item\s+)?(?:\d+[A-Za-z]?|[A-Za-z])\s*[\.\-:]*\s*[A-Za-z\s]+',
        re.IGNORECASE
    )
    
    for element in soup.find_all(string=True):
        if not isinstance(element.parent, Tag):
            continue
            
        text = element.get_text(strip=True)
        if header_pattern.match(text):
            # Try to determine header level based on formatting
            parent = element.parent
            level = 1  # Default level
            
            # Check if parent has any heading tags
            if parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(parent.name[1])
            
            # Try to extract page number if available
            page = None
            page_attr = parent.get('data-page', None)
            if page_attr:
                try:
                    page = int(page_attr)
                except ValueError:
                    pass
            
            headers.append({
                "text": text,
                "level": level,
                "page": page
            })
    
    return headers