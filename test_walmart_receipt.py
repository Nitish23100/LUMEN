#!/usr/bin/env python3
"""
Test with the actual Walmart receipt
"""

import ai_extractor
import json

def test_walmart_receipt():
    """Test with the actual Walmart receipt image"""
    
    print("Testing with Walmart Receipt...")
    print("=" * 50)
    
    # Test with the bill2.jpg file
    test_image = "uploads/20251114_171748_bill2.jpg"
    
    result = ai_extractor.extract_from_image(test_image)
    
    if result:
        print("✓ Walmart receipt analysis successful!")
        print(f"  Vendor: {result.get('vendor')}")
        print(f"  Date: {result.get('date')}")
        print(f"  Total: ${result.get('total')}")
        print(f"  Items: {len(result.get('items', []))} items")
        print(f"  Payment: {result.get('payment_method')}")
        print(f"  Method: {result.get('extraction_method')}")
        print(f"  Confidence: {result.get('confidence_score')}%")
        
        print("\nItems purchased:")
        for item in result.get('items', []):
            print(f"  - {item.get('name')}: ${item.get('price')}")
        
        if result.get('total') == 90.32:
            print("\n🎉 Perfect match with your actual receipt!")
        else:
            print(f"\nℹ️ Analyzed receipt (Total: ${result.get('total')})")
    else:
        print("✗ Extraction failed")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_walmart_receipt()