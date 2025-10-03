import io
from typing import Optional
from docx import Document
import PyPDF2

def process_text_file(uploaded_file) -> str:
    """Process a plain text file"""
    try:
        # Try UTF-8 first
        content = uploaded_file.read().decode('utf-8')
        return content
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        uploaded_file.seek(0)
        content = uploaded_file.read().decode('latin-1')
        return content

def process_docx_file(uploaded_file) -> str:
    """Process a Word document file"""
    try:
        doc = Document(uploaded_file)
        content = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                content.append(paragraph.text)
        
        return '\n'.join(content)
    except Exception as e:
        raise ValueError(f"Error processing DOCX file: {str(e)}")

def process_pdf_file(uploaded_file) -> str:
    """Process a PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        content = []
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text.strip():
                content.append(text)
        
        return '\n'.join(content)
    except Exception as e:
        raise ValueError(f"Error processing PDF file: {str(e)}")

def process_uploaded_file(uploaded_file) -> tuple[str, str]:
    """
    Process an uploaded file based on its type
    Returns: (content, error_message)
    """
    if uploaded_file is None:
        return "", "No file uploaded"
    
    file_type = uploaded_file.type
    filename = uploaded_file.name
    
    try:
        if file_type == "text/plain" or filename.endswith('.txt'):
            content = process_text_file(uploaded_file)
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.endswith('.docx'):
            content = process_docx_file(uploaded_file)
        elif file_type == "application/pdf" or filename.endswith('.pdf'):
            content = process_pdf_file(uploaded_file)
        else:
            return "", f"Unsupported file type: {file_type}"
        
        if not content.strip():
            return "", "File appears to be empty or contains no readable text"
        
        return content, ""
    
    except Exception as e:
        return "", f"Error processing file: {str(e)}"

def get_file_preview(content: str, max_chars: int = 500) -> str:
    """Get a preview of the file content"""
    if len(content) <= max_chars:
        return content
    
    preview = content[:max_chars]
    # Try to cut at a word boundary
    last_space = preview.rfind(' ')
    if last_space > max_chars * 0.8:  # If we find a space in the last 20%
        preview = preview[:last_space]
    
    return preview + "..."

def validate_file_size(uploaded_file, max_size_mb: int = 10) -> tuple[bool, str]:
    """Validate file size"""
    if uploaded_file.size > max_size_mb * 1024 * 1024:
        return False, f"File size ({uploaded_file.size / 1024 / 1024:.1f} MB) exceeds maximum allowed size of {max_size_mb} MB"
    return True, ""