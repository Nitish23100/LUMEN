#!/usr/bin/env python3
"""
Test NVIDIA AI extractor
"""

import ai_extractor
import json

def test_nvidia_extractor():
    """Test the NVIDIA-based extractor"""
    
    print("Testing NVIDIA AI Extractor...")
    print("=" * 50)
    
    # Test text extraction
    sample_text = """
    WALMART SUPERCENTER
    Date: 2024-01-15
    Total: $25.99
    """
    
    result = ai_extractor.extract_from_text(sample_text)
    
    if result:
        print("✓ Extraction successful!")
        print(f"  Vendor: {result.get('vendor')}")
        print(f"  Total: ${result.get('total')}")
        print(f"  Method: {result.get('extraction_method')}")
        print(f"  Confidence: {result.get('confidence_score')}%")
    else:
        print("✗ Extraction failed")
    
    print("\n" + "=" * 50)
    print("Your Flask app should now work with this extractor!")

if __name__ == "__main__":
    test_nvidia_extractor()