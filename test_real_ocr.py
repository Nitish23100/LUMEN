#!/usr/bin/env python3
"""
Test OCR functionality with a real image
"""

import ai_extractor
import json
import os

def test_ocr_with_real_image():
    """Test OCR with an actual uploaded image"""
    
    print("Testing OCR with Real Images...")
    print("=" * 50)
    
    # Check if there are any uploaded images
    uploads_dir = "uploads"
    if os.path.exists(uploads_dir):
        image_files = [f for f in os.listdir(uploads_dir) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        
        if image_files:
            # Test with the first image found
            test_image = os.path.join(uploads_dir, image_files[0])
            print(f"Testing with: {test_image}")
            
            result = ai_extractor.extract_from_image(test_image)
            
            if result:
                print("✓ OCR extraction successful!")
                print(f"  Vendor: {result.get('vendor')}")
                print(f"  Date: {result.get('date')}")
                print(f"  Total: ${result.get('total')}")
                print(f"  Method: {result.get('extraction_method')}")
                print(f"  Confidence: {result.get('confidence_score')}%")
                
                if result.get('extraction_method') == 'simple_ocr':
                    print("🎉 Real OCR analysis working!")
                else:
                    print("ℹ️ Using fallback data (OCR may have failed)")
            else:
                print("✗ Extraction failed")
        else:
            print("No image files found in uploads/ directory")
            print("Upload an image through the web interface first")
    else:
        print("uploads/ directory not found")
        print("Upload an image through the web interface first")
    
    print("\n" + "=" * 50)
    print("Now your Flask app should analyze real receipts!")
    print("The system will:")
    print("1. Try Gemini API first (if working)")
    print("2. Fall back to EasyOCR (real analysis)")
    print("3. Use mock data only as last resort")

if __name__ == "__main__":
    test_ocr_with_real_image()