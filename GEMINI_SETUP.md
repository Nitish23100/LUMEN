# Google Gemini API Setup for LUMEN

## Getting Your Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key
5. Add it to your `.env` file:
   ```
   GEMINI_API_KEY=your-actual-api-key-here
   ```

## Supported Features

The LUMEN AI extractor uses Google Gemini 1.5 Flash model for:

- **Image Analysis**: Extract financial data from receipt/invoice images (JPG, PNG, GIF, WebP)
- **PDF Processing**: Extract text from PDFs and analyze financial data
- **Text Analysis**: Direct text processing for receipt data

## Usage

```python
from ai_extractor import extract_from_image, extract_from_pdf, extract_from_text, process_uploaded_file

# Extract from image
result = extract_from_image("receipt.jpg")

# Extract from PDF
result = extract_from_pdf("invoice.pdf")

# Extract from text
result = extract_from_text("receipt text content...")

# Auto-detect file type and process
result = process_uploaded_file("path/to/file")
```

## Extracted Data Format

```json
{
  "vendor": "Store Name",
  "date": "2024-01-15",
  "items": [
    {"name": "Item Name", "price": 9.99}
  ],
  "subtotal": 45.99,
  "tax": 3.68,
  "total": 49.67,
  "category": "groceries",
  "payment_method": "credit",
  "confidence_score": 85,
  "extraction_method": "gemini_vision",
  "source_file": "receipt.jpg"
}
```

## Error Handling

The system includes robust error handling for:
- Invalid API keys
- Quota exceeded errors
- Unsupported file formats
- Network connectivity issues
- JSON parsing errors

When the API is unavailable, the system falls back to mock data for testing purposes.