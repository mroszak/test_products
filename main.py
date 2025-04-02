import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
import json

# Load environment variables
load_dotenv()

def search_products(query, min_price=None, max_price=None, sort_by=None):
    """
    Search for products on Google Shopping
    
    Args:
        query (str): Search query
        min_price (float, optional): Minimum price filter
        max_price (float, optional): Maximum price filter
        sort_by (str, optional): Sort results by (price, rating, etc.)
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("Error: Please set your SERPAPI_KEY in the .env file")
        return []

    params = {
        "api_key": api_key,
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.com"
    }
    
    # Add optional parameters
    if min_price:
        params["price_low"] = min_price
    if max_price:
        params["price_high"] = max_price
    if sort_by:
        params["sort_by"] = sort_by
    
    try:
        print(f"Searching for: {query}")
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            print(f"API Error: {results['error']}")
            return []
            
        shopping_results = results.get("shopping_results", [])
        if not shopping_results:
            print("No results found")
            return []
            
        return shopping_results
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return []

def main():
    # Example usage
    query = "laptop"
    results = search_products(query, min_price=500, max_price=1000, sort_by="price")
    
    if not results:
        print("No results to display")
        return

    # Print all available fields from the first result
    if results:
        print("\nAvailable fields in the API response:")
        first_result = results[0]
        for key, value in first_result.items():
            print(f"\n{key}:")
            print(f"  Type: {type(value).__name__}")
            print(f"  Value: {value}")
        
        # Print full JSON of first result for reference
        print("\nFull JSON structure of first result:")
        print(json.dumps(first_result, indent=2))
        
        # Print summary of all results
        print(f"\nFound {len(results)} results:")
        for product in results:
            print(f"\nProduct: {product.get('title')}")
            print(f"Price: {product.get('price')}")
            print(f"Rating: {product.get('rating')}")
            print(f"Reviews: {product.get('reviews')}")
            print(f"Link: {product.get('link')}")
            print(f"Source: {product.get('source')}")
            print(f"Shipping: {product.get('shipping')}")
            if product.get('extensions'):
                print(f"Additional Info: {', '.join(product.get('extensions'))}")

if __name__ == "__main__":
    main() 