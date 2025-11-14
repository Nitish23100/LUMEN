#!/usr/bin/env python3
"""
Test script for LUMEN upload functionality
"""

import requests
import json
import os

def test_text_upload():
    """Test uploading a text file with receipt data"""
    
    # Create a sample receipt text file
    sample_receipt = """
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
    
    # Save to a temporary file
    test_file_path = 'uploads/test_receipt.txt'
    with open(test_file_path, 'w') as f:
        f.write(sample_receipt)
    
    print("✓ Created test receipt file")
    
    # Test the upload endpoint
    url = 'http://127.0.0.1:5000/upload'
    
    try:
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test_receipt.txt', f, 'text/plain')}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✓ Upload successful!")
                print(f"✓ Transaction ID: {data['data']['transaction_id']}")
                print(f"✓ Vendor: {data['data']['vendor']}")
                print(f"✓ Amount: ${data['data']['total']}")
                print(f"✓ Confidence: {data['data']['confidence_score']}%")
                
                # Test preview endpoint
                transaction_id = data['data']['transaction_id']
                preview_url = f'http://127.0.0.1:5000/preview/{transaction_id}'
                preview_response = requests.get(preview_url)
                
                if preview_response.status_code == 200:
                    print("✓ Preview page accessible")
                else:
                    print(f"✗ Preview page error: {preview_response.status_code}")
                
            else:
                print(f"✗ Upload failed: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection error. Make sure Flask app is running on http://127.0.0.1:5000")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Clean up
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print("✓ Cleaned up test file")

if __name__ == "__main__":
    print("Testing LUMEN upload functionality...")
    print("Make sure the Flask app is running first!")
    print("-" * 50)
    test_text_upload()