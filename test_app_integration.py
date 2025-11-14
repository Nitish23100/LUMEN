#!/usr/bin/env python3
"""
Test Flask app integration with database and AI extractor
"""

import requests
import json
import os
import time

def test_app_integration():
    """Test the complete Flask app integration"""
    
    print("Testing Flask App Integration...")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:5000"
    
    # Test 1: Check if app is running
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✓ Flask app is running")
        else:
            print("✗ Flask app not responding")
            return
    except requests.exceptions.ConnectionError:
        print("✗ Flask app not running. Start it with: python app.py")
        return
    
    # Test 2: Test file upload with a simple text file
    print("\n2. Testing file upload...")
    
    # Create a test receipt text file
    test_content = """
    WALMART SUPERCENTER
    Store #1234
    Date: 2024-01-15
    
    Milk 2% Gallon         $3.99
    Bread Whole Wheat      $2.49
    
    Subtotal:             $6.48
    Tax:                   $0.52
    Total:                $7.00
    
    Payment: CREDIT CARD
    """
    
    test_file_path = "test_receipt.txt"
    with open(test_file_path, 'w') as f:
        f.write(test_content)
    
    try:
        # Upload the test file
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test_receipt.txt', f, 'text/plain')}
            response = requests.post(f"{base_url}/upload", files=files)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✓ File upload successful")
                transaction_id = data['data']['transaction_id']
                print(f"  Transaction ID: {transaction_id}")
                
                # Test 3: Retrieve the transaction
                print(f"\n3. Testing transaction retrieval...")
                response = requests.get(f"{base_url}/transaction/{transaction_id}")
                
                if response.status_code == 200:
                    transaction_data = response.json()
                    if transaction_data.get('success'):
                        print("✓ Transaction retrieval successful")
                        print(f"  Vendor: {transaction_data['data']['vendor']}")
                        print(f"  Total: ${transaction_data['data']['amount']}")
                        print(f"  Method: {transaction_data['data'].get('extraction_method', 'N/A')}")
                    else:
                        print("✗ Transaction retrieval failed")
                else:
                    print(f"✗ Transaction API error: {response.status_code}")
            else:
                print(f"✗ Upload failed: {data.get('error')}")
        else:
            print(f"✗ Upload HTTP error: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"✗ Test error: {e}")
    
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    print("\n" + "=" * 50)
    print("Integration test complete!")

if __name__ == "__main__":
    test_app_integration()