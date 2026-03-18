import fitz  # PyMuPDF
import re
from pathlib import Path

def extract_text_from_pdf(pdf_path: str) -> dict:
    """
    Extract clean text from PDF using PyMuPDF
    Returns dict with full text, pages, and metadata
    """
    doc = fitz.open(pdf_path)
    
    full_text = ""
    pages_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        pages_text.append({
            "page_number": page_num + 1,
            "text": page_text
        })
        full_text += page_text + "\n"
    
    doc.close()
    
    return {
        "full_text": full_text,
        "pages": pages_text,
        "total_pages": len(pages_text),
        "total_chars": len(full_text)
    }


def clean_text(text: str) -> str:
    """
    Clean extracted text for NLP processing
    """
    # Remove excessive whitespace
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove special characters but keep punctuation
    text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
    
    # Remove very short lines (page numbers, headers)
    lines = text.split('\n')
    cleaned_lines = [
        line.strip() for line in lines 
        if len(line.strip()) > 10
    ]
    
    return '\n'.join(cleaned_lines)


def extract_sentences(text: str) -> list:
    """
    Split text into clean sentences
    """
    import spacy
    nlp = spacy.load("en_core_web_lg")
    doc = nlp(text[:100000])  # Limit to 100k chars for speed
    
    sentences = [
        sent.text.strip() 
        for sent in doc.sents 
        if len(sent.text.strip()) > 20
    ]
    
    return sentences