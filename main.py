import os
from dotenv import load_dotenv
import requests
from pprint import pprint

# Load environment variables
load_dotenv()

def search_products(query, page=1, country='us'):
    """
    Search for products using Oxylabs API
    
    Args:
        query (str): Search query
        page (int, optional): Page number for pagination
        country (str, optional): Country code
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")
    if not username or not password:
        print("Error: Please set your OXYLABS_USERNAME and OXYLABS_PASSWORD in the .env file")
        return []

    # Structure payload.
    payload = {
        'source': 'amazon',
        'query': query,
        'page': page,
        'country': country
    }

    try:
        print(f"Searching for: {query}")
        # Get response.
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=(username, password),
            json=payload,
        )
        
        response.raise_for_status()  # Raise exception for bad status codes
        
        results = response.json()
        print(results)
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"API Error occurred: {str(e)}")
        return []
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return []

def main():
    # Example usage
    query = "iphone x"
    results = search_products(query)
    
    if not results:
        print("No results to display")
        return

if __name__ == "__main__":
    main() 