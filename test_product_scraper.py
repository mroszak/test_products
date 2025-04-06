import os
import sys
import json
import argparse
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

def get_product_details(product_id):
    """
    Get details for a specific Amazon product using Oxylabs API
    
    Args:
        product_id (str): Amazon ASIN/product ID
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")
    
    if not username or not password:
        print("Error: Please set your OXYLABS_USERNAME and OXYLABS_PASSWORD in the .env file")
        return None
    
    print(f"Getting details for product ID: {product_id}")
    
    # Structure payload for Oxylabs API
    payload = {
        'source': 'amazon',
        'domain': 'com',
        'url': f'https://www.amazon.com/dp/{product_id}',
        'parse': True
    }
    
    try:
        print(f"Sending request to Oxylabs API...")
        # Get response
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=(username, password),
            json=payload,
        )
        
        # Print the request payload for debugging
        print(f"Request payload: {json.dumps(payload, indent=2)}")
        
        # Check for error response
        if response.status_code >= 400:
            print(f"Error response ({response.status_code}):")
            try:
                error_json = response.json()
                print(json.dumps(error_json, indent=2))
            except:
                print(response.text)
        
        response.raise_for_status()
        print(f"Response status code: {response.status_code}")
        
        results = response.json()
        
        print("Full API response:")
        print(json.dumps(results, indent=2))
        
        if not results or "results" not in results:
            print("No results found in API response")
            return None
            
        # Extract content from the response
        if not results["results"] or "content" not in results["results"][0]:
            print("No content in results")
            return None
        
        content = results["results"][0]["content"]
        print(f"Product data retrieved successfully")
        
        # Check for parse status code
        if isinstance(content, dict) and content.get('parse_status_code') == 12003:
            print("WARNING: Product not found on Amazon or is currently unavailable")
            print("This could be due to:")
            print("1. The product ASIN is no longer valid")
            print("2. The product is not available in the region used for scraping")
            print("3. Amazon is blocking the scraping request")
        
        return content
        
    except requests.exceptions.RequestException as e:
        print(f"API Error occurred: {str(e)}")
        return None
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Fetch Amazon product details by ASIN')
    parser.add_argument('asin', help='Amazon ASIN (10-character product ID)')
    parser.add_argument('--output', '-o', help='Output file path (optional)')
    args = parser.parse_args()
    
    # Validate ASIN format (10 alphanumeric characters)
    import re
    if not re.match(r'^[A-Z0-9]{10}$', args.asin):
        print("Error: Invalid ASIN format. Amazon ASIN should be 10 alphanumeric characters.")
        sys.exit(1)
    
    product_data = get_product_details(args.asin)
    
    if not product_data:
        print(f"Failed to retrieve product data for ASIN: {args.asin}")
        sys.exit(1)
    
    # Output the data
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(product_data, f, indent=2)
        print(f"Product data saved to {args.output}")
    else:
        # Pretty print to console
        print(json.dumps(product_data, indent=2))
    
    print(f"Successfully retrieved product data for ASIN: {args.asin}")

if __name__ == "__main__":
    main() 