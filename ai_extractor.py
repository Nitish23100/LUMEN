import os
import base64
import json
import logging
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from openai import OpenAI
import PyPDF2
from PIL import Image

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NVIDIA API configuration
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.2-11b-vision-instruct"

# System prompt for financial data extraction
EXTRACTION_PROMPT = """You are a financial OCR expert. Extract data from this receipt image and return ONLY valid JSON with these exact fields: vendor, date (YYYY-MM-DD), items (array of {name, price}), subtotal, tax, total, category (groceries/dining/transportation/utilities/entertainment/shopping/healthcare/other), payment_method, confidence_score (0-100). No markdown, no explanation, just JSON."""

def get_nvidia_client():
    """Initialize NVIDIA API client."""
    api_key = os.getenv('NVIDIA_API_KEY')
    if not api_key:
        logger.error("NVIDIA_API_KEY not found in environment variables")
        return None
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=NVIDIA_API_BASE
        )
        logger.info("NVIDIA API client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize NVIDIA API client: {e}")
        return None

def encode_image_to_base64(image_path: str) -> Optional[str]:
    """
    Convert an image file to base64 encoding.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Base64 encoded string or None if error
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}")
        return None

def validate_extracted_data(data: Dict[str, Any]) -> bool:
    """
    Validate that extracted data contains required fields.
    
    Args:
        data: Dictionary containing extracted data
        
    Returns:
        True if data is valid, False otherwise
    """
    required_fields = ['vendor', 'date', 'total', 'category', 'confidence_score']
    
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return False
    
    # Validate confidence score
    if not isinstance(data.get('confidence_score'), (int, float)) or not (0 <= data['confidence_score'] <= 100):
        logger.warning("Invalid confidence_score")
        return False
    
    # Validate category (normalize to lowercase)
    valid_categories = ['groceries', 'dining', 'transportation', 'utilities', 'entertainment', 'shopping', 'healthcare', 'other']
    category = data.get('category', '').lower()
    if category not in valid_categories:
        logger.warning(f"Invalid category: {data.get('category')}")
        return False
    
    # Normalize category to lowercase
    data['category'] = category
    
    return True

def extract_from_image(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract financial data from receipt image using NVIDIA Nemotron Nano 2 VL model.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Dictionary containing extracted financial data or None if extraction fails
    """
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
        
        # Get NVIDIA API client
        client = get_nvidia_client()
        if not client:
            return None
        
        # Encode image to base64
        base64_image = encode_image_to_base64(image_path)
        if not base64_image:
            return None
        
        # Determine image format
        image_format = image_path.lower().split('.')[-1]
        if image_format not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            logger.error(f"Unsupported image format: {image_format}")
            return None
        
        logger.info(f"Processing image with NVIDIA Nemotron: {image_path}")
        
        # Call NVIDIA API
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        # Extract response content
        content = response.choices[0].message.content.strip()
        logger.info(f"NVIDIA API response received: {len(content)} characters")
        
        # Clean up response (remove markdown and extract JSON)
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '').strip()
        elif content.startswith('```'):
            content = content.replace('```', '').strip()
        
        # Extract JSON from response if it contains extra text
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            content = content[json_start:json_end].strip()
            logger.info(f"Extracted JSON portion: {len(content)} characters")
        
        # Parse JSON response
        try:
            extracted_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {content}")
            return None
        
        # Validate extracted data
        if not validate_extracted_data(extracted_data):
            logger.error("Extracted data validation failed")
            return None
        
        # Add metadata
        extracted_data['extraction_method'] = 'nvidia_nemotron'
        extracted_data['source_file'] = image_path
        
        logger.info(f"Successfully extracted data using NVIDIA Nemotron - Vendor: {extracted_data.get('vendor')}, Total: ${extracted_data.get('total')}")
        return extracted_data
        
    except Exception as e:
        logger.error(f"Error extracting data from image using NVIDIA API: {e}")
        return None

def extract_from_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract financial data from PDF using PyPDF2 and NVIDIA Nemotron.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary containing extracted financial data or None if extraction fails
    """
    try:
        # Check if file exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        # Extract text from PDF
        text_content = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
        
        if not text_content.strip():
            logger.error("No text content extracted from PDF")
            return None
        
        logger.info(f"Extracted {len(text_content)} characters from PDF")
        
        # Use text extraction function
        result = extract_from_text(text_content)
        
        if result:
            result['extraction_method'] = 'nvidia_pdf'
            result['source_file'] = pdf_path
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {e}")
        return None

def extract_from_text(text_content: str) -> Optional[Dict[str, Any]]:
    """
    Extract financial data from text content using NVIDIA Nemotron.
    
    Args:
        text_content: Text content to analyze
        
    Returns:
        Dictionary containing extracted financial data or None if extraction fails
    """
    try:
        # Get NVIDIA API client
        client = get_nvidia_client()
        if not client:
            return None
        
        if not text_content.strip():
            logger.error("Empty text content provided")
            return None
        
        # Prepare prompt for text analysis
        text_prompt = f"{EXTRACTION_PROMPT}\n\nReceipt text to analyze:\n{text_content}"
        
        logger.info("Processing text with NVIDIA Nemotron")
        
        # Call NVIDIA API for text processing
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": text_prompt
                }
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        # Extract response content
        content = response.choices[0].message.content.strip()
        logger.info(f"NVIDIA API text response received: {len(content)} characters")
        
        # Clean up response (remove markdown and extract JSON)
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '').strip()
        elif content.startswith('```'):
            content = content.replace('```', '').strip()
        
        # Extract JSON from response if it contains extra text
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            content = content[json_start:json_end].strip()
            logger.info(f"Extracted JSON portion: {len(content)} characters")
        
        # Parse JSON response
        try:
            extracted_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {content}")
            return None
        
        # Validate extracted data
        if not validate_extracted_data(extracted_data):
            logger.error("Extracted data validation failed")
            return None
        
        # Add metadata
        extracted_data['extraction_method'] = 'nvidia_text'
        
        logger.info(f"Successfully extracted data from text using NVIDIA Nemotron - Vendor: {extracted_data.get('vendor')}, Total: ${extracted_data.get('total')}")
        return extracted_data
        
    except Exception as e:
        logger.error(f"Error extracting data from text using NVIDIA API: {e}")
        return None

def process_uploaded_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Process an uploaded file and extract financial data.
    
    Args:
        file_path: Path to the uploaded file
        
    Returns:
        Dictionary containing extracted financial data or None if extraction fails
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None
    
    # Get file extension
    file_ext = file_path.lower().split('.')[-1]
    
    # Route to appropriate extraction function
    if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        logger.info(f"Processing image file: {file_path}")
        return extract_from_image(file_path)
    elif file_ext == 'pdf':
        logger.info(f"Processing PDF file: {file_path}")
        return extract_from_pdf(file_path)
    elif file_ext in ['txt', 'text']:
        logger.info(f"Processing text file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        return extract_from_text(text_content)
    else:
        logger.error(f"Unsupported file format: {file_ext}")
        return None

def test_extraction():
    """Test function to verify the extraction functionality."""
    print("Testing NVIDIA Nemotron AI extraction functions...")
    
    # Test text extraction with sample receipt text
    sample_text = """
    WALMART SUPERCENTER
    Store #1234
    123 Main St, Anytown, USA
    
    Date: 2024-01-15
    Time: 14:30
    
    GROCERIES:
    Milk 2% Gallon         $3.99
    Bread Whole Wheat      $2.49
    Bananas 2 lbs          $1.98
    Chicken Breast 1 lb    $5.99
    
    Subtotal:             $14.45
    Tax:                   $1.16
    Total:                $15.61
    
    Payment: CREDIT CARD
    """
    
    result = extract_from_text(sample_text)
    if result:
        print("✓ NVIDIA Nemotron text extraction successful")
        print(json.dumps(result, indent=2))
    else:
        print("✗ NVIDIA Nemotron text extraction failed")

if __name__ == "__main__":
    test_extraction()