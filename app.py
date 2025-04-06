from flask import Flask, render_template, request, send_file, jsonify
from dotenv import load_dotenv
import os
import tempfile
import logging
import json
import re
from urllib.parse import urlparse, parse_qsl
from functools import lru_cache
import string
import requests
import pandas as pd
import random
from bs4 import BeautifulSoup
import io
from flask_cors import CORS

app = Flask(__name__)
load_dotenv()
CORS(app)

# Initialize logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Retailer URL patterns
RETAILER_PATTERNS = {
    'amazon.com': {
        'pattern': 'https://www.amazon.com/dp/{product_id}',
        'id_regex': r'/dp/([A-Z0-9]{10})'
    },
    'walmart.com': {
        'pattern': 'https://www.walmart.com/ip/{product_id}',
        'id_regex': r'/ip/(\d+)'
    },
    'bestbuy.com': {
        'pattern': 'https://www.bestbuy.com/site/{product_id}',
        'id_regex': r'/site/([A-Za-z0-9-]+)'
    },
    'target.com': {
        'pattern': 'https://www.target.com/p/{product_id}',
        'id_regex': r'/p/([A-Za-z0-9-]+)'
    }
}

@lru_cache(maxsize=1000)
def get_retailer_pattern(domain):
    """Cache retailer URL patterns"""
    for retailer_domain, pattern in RETAILER_PATTERNS.items():
        if retailer_domain in domain.lower():
            return pattern
    return None

def validate_product_url(url):
    """Validate the generated product URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_retailer_specific_url(product):
    """Get URL using retailer-specific patterns"""
    source = product.get('source', '').lower()
    link = product.get('link', '')
    
    pattern = get_retailer_pattern(source)
    if pattern:
        # Try to extract product ID using regex
        match = re.search(pattern['id_regex'], link)
        if match:
            product_id = match.group(1)
            return pattern['pattern'].format(product_id=product_id)
    return None

def validate_url(url):
    """Enhanced URL validation"""
    try:
        result = urlparse(url)
        checks = {
            'has_scheme': bool(result.scheme),
            'has_netloc': bool(result.netloc),
            'valid_scheme': result.scheme in ['http', 'https'],
            'has_path': bool(result.path),
            'no_fragments': not result.fragment,  # Most product URLs don't need fragments
            'valid_chars': all(c in string.printable for c in url)
        }
        
        is_valid = all(checks.values())
        return {
            'is_valid': is_valid,
            'checks': checks,
            'error': None if is_valid else 'URL validation failed: ' + ', '.join(k for k, v in checks.items() if not v)
        }
    except Exception as e:
        return {
            'is_valid': False,
            'checks': {},
            'error': str(e)
        }

def extract_domain(url):
    """Extract domain from URL"""
    try:
        return urlparse(url).netloc.lower()
    except:
        return None

def search_products(query, min_price=None, max_price=None, sort_by=None):
    """
    Search for products using Oxylabs API
    
    Args:
        query (str): Search query
        min_price (float, optional): Minimum price filter
        max_price (float, optional): Maximum price filter
        sort_by (str, optional): Sort results by (price, rating, etc.)
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")
    
    print(f"Searching for: {query}")
    print(f"Using credentials - Username: {username}, Password: {password[:3]}***")
    
    # Structure payload for Oxylabs API
    payload = {
        'source': 'amazon_search',
        'domain': 'com',
        'query': query,
        'parse': True,
        'zip_code': '90210'  # Using zip code for US location
    }
    
    try:
        print(f"Sending request to Oxylabs API...")
        # Get response.
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=(username, password),
            json=payload,
        )
        
        response.raise_for_status()  # Raise exception for bad status codes
        
        print(f"Status code: {response.status_code}")
        print(f"Response content type: {response.headers.get('Content-Type')}")
        
        results = response.json()
        print(f"Response keys: {results.keys() if results else 'None'}")
        
        if not results or "results" not in results:
            print("No results found in API response")
            return []
        
        print(f"Number of results: {len(results['results'])}")
            
        # Extract content from the response
        if not results["results"] or "content" not in results["results"][0]:
            print("No content in results")
            return []
        
        content = results["results"][0]["content"]
        print(f"Content keys: {content.keys() if isinstance(content, dict) else 'Not a dict'}")
        
        # Parse Amazon search results 
        product_listings = []
        
        # Check for the correct Amazon results structure
        if isinstance(content, dict):
            # Amazon search results are structured as content.results.organic
            results_container = content.get("results", {})
            if isinstance(results_container, dict) and "organic" in results_container:
                items = results_container.get("organic", [])
                print(f"Found {len(items)} organic items")
                
                # DEBUG: Print raw format of the first item to understand structure
                if items and len(items) > 0:
                    print(f"DEBUG: First item raw format: {json.dumps(items[0], indent=2)}")
                
                for i, item in enumerate(items):
                    try:
                        # Extract title (this has a different format in Amazon search)
                        title = item.get("title", "No title available")
                        
                        # Extract URL (this is a relative URL in Amazon search)
                        url = item.get("url", "")
                        if url and url.startswith("/"):
                            url = f"https://www.amazon.com{url}"
                        
                        # Extract price
                        price_text = "Price not available"
                        extracted_price = 0
                        if "price" in item:
                            try:
                                # Direct price field as a number
                                if isinstance(item["price"], (int, float)):
                                    extracted_price = float(item["price"])
                                    price_text = f"${extracted_price:.2f}"
                                # Price as a dict object (older format)
                                elif isinstance(item["price"], dict):
                                    price_obj = item.get("price", {})
                                    price_text = price_obj.get("raw", price_obj.get("value", "Price not available"))
                                    if "value" in price_obj:
                                        extracted_price = float(price_obj.get("value", 0))
                                    elif "raw" in price_obj:
                                        raw_price = price_obj.get("raw", "")
                                        # Extract numeric part from formats like "$19.99" or "19,99 €"
                                        numeric_part = re.sub(r'[^\d\.]', '', raw_price.replace(',', '.'))
                                        if numeric_part:
                                            extracted_price = float(numeric_part)
                            except (ValueError, TypeError) as e:
                                print(f"Error parsing price: {e}")
                        # Check for price displayed in the title
                        elif not price_text or price_text == "Price not available":
                            title_price_match = re.search(r'\$(\d+(?:\.\d+)?)', title)
                            if title_price_match:
                                price_text = f"${title_price_match.group(1)}"
                                extracted_price = float(title_price_match.group(1))
                        
                        # Extract rating
                        rating = 0
                        if "rating" in item:
                            try:
                                rating_val = item.get("rating", 0)
                                if isinstance(rating_val, (int, float)):
                                    rating = float(rating_val)
                                elif isinstance(rating_val, dict) and "value" in rating_val:
                                    rating = float(rating_val.get("value", 0))
                            except (ValueError, TypeError):
                                rating = 0
                        
                        # Extract review count
                        review_count = 0
                        if "reviews_count" in item:
                            try:
                                review_count = int(item["reviews_count"])
                            except (ValueError, TypeError):
                                review_count = 0
                        elif "reviews" in item:
                            try:
                                reviews_val = item.get("reviews", 0)
                                if isinstance(reviews_val, (int, str)):
                                    review_count = int(str(reviews_val).replace(',', '').replace('.', '').strip())
                                elif isinstance(reviews_val, dict) and "value" in reviews_val:
                                    review_count = int(reviews_val.get("value", 0))
                            except (ValueError, TypeError):
                                review_count = 0
                        
                        # Try to extract review count from title if it's not found elsewhere
                        if review_count == 0:
                            # Look for patterns like "1,234 reviews" or "(1,234)"
                            review_match = re.search(r'(\d+(?:,\d+)*)\s*(?:reviews|ratings|\(|\)|stars)', title, re.IGNORECASE)
                            if review_match:
                                review_count = int(review_match.group(1).replace(',', ''))
                        
                        # Extract image URL
                        image_url = ""
                        if "url_image" in item:
                            image_url = item.get("url_image", "")
                        elif "image" in item:
                            image_url = item.get("image", "")
                        # Sometimes the image is nested in the thumbnail field
                        elif "thumbnail" in item:
                            image_url = item.get("thumbnail", "")
                            
                        # For Amazon search, images might be in various formats
                        if not image_url and "variants" in item:
                            variants = item.get("variants", [])
                            for variant in variants:
                                if "image" in variant:
                                    image_url = variant.get("image", "")
                                    break
                        
                        # If still no image, use a placeholder
                        if not image_url:
                            image_url = f"https://via.placeholder.com/300x300?text=Amazon+Product"
                        
                        # Extract product ID (ASIN)
                        product_id = ""
                        if "asin" in item:
                            product_id = item.get("asin", "")
                        elif url:
                            # Try to extract ASIN from URL
                            asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
                            if asin_match:
                                product_id = asin_match.group(1)
                        
                        # Create a rich description by combining multiple fields
                        description_parts = []
                        
                        # Add sales volume if available
                        if item.get("sales_volume"):
                            description_parts.append(item.get("sales_volume"))
                            
                        # Add bestseller status if true
                        if item.get("best_seller"):
                            description_parts.append("Best Seller")
                            
                        # Add Amazon's Choice status if true
                        if item.get("is_amazons_choice"):
                            description_parts.append("Amazon's Choice")
                            
                        # Add Prime status if true
                        if item.get("is_prime"):
                            description_parts.append("Prime Eligible")
                            
                        # Add manufacturer if available
                        if item.get("manufacturer"):
                            description_parts.append(f"By {item.get('manufacturer')}")
                            
                        # Combine all parts into a description
                        description = " | ".join(description_parts)
                        
                        # Build product data
                        product_data = {
                            "position": i + 1,
                            "title": title,
                            "link": url,
                            "price": price_text,
                            "extracted_price": extracted_price,
                            "rating": rating,
                            "ratingCount": review_count,
                            "imageUrl": image_url,
                            "thumbnail": image_url,
                            "description": description,
                            "source": "amazon.com",
                            "delivery": item.get("shipping_information", ""),
                            "productId": product_id,
                        }
                        
                        product_listings.append(product_data)
                    except Exception as e:
                        print(f"Error processing item: {str(e)}")
                        continue
            elif "organic_results" in content:
                # Old format support (just in case)
                items = content.get("organic_results", [])
                print(f"Found {len(items)} organic_results items")
            
        print(f"Successfully extracted {len(product_listings)} products")
        
        # Apply filters if specified
        if min_price is not None:
            product_listings = [p for p in product_listings if p["extracted_price"] >= float(min_price)]
        
        if max_price is not None:
            product_listings = [p for p in product_listings if p["extracted_price"] <= float(max_price)]
        
        if sort_by == "price_asc":
            product_listings.sort(key=lambda p: p["extracted_price"])
        elif sort_by == "price_desc":
            product_listings.sort(key=lambda p: p["extracted_price"], reverse=True)
        elif sort_by == "rating":
            product_listings.sort(key=lambda p: p["rating"], reverse=True)
        
        return product_listings
        
    except requests.exceptions.RequestException as e:
        print(f"API Error occurred: {str(e)}")
        return []
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    try:
        if request.method == 'POST':
            query = request.form.get('query', '')
            format_type = request.form.get('format', 'json')
            
            # Handle Excel export
            if format_type.lower() == 'excel':
                # Get the selected rows passed from the frontend
                selected_rows_json = request.form.get('selected_rows', '[]')
                visible_columns_json = request.form.get('visible_columns', '[]')
                is_detailed = request.form.get('is_detailed', 'false').lower() == 'true'
                
                try:
                    selected_rows = json.loads(selected_rows_json)
                    visible_columns = json.loads(visible_columns_json) if visible_columns_json else []
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid JSON data"}), 400
                
                # Create DataFrame
                df = pd.DataFrame(selected_rows)
                
                # Filter columns if provided
                if visible_columns:
                    available_columns = [col for col in visible_columns if col in df.columns]
                    df = df[available_columns]
                
                # Create Excel file in memory
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    sheet_name = "Detailed Product Data" if is_detailed else "Search Results"
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
                    
                    # Auto-adjust columns' width
                    worksheet = writer.sheets[sheet_name]
                    for i, col in enumerate(df.columns):
                        # Avoid adjusting too wide for large content columns
                        max_length = min(max(df[col].astype(str).apply(len).max(), len(col)) + 2, 50)
                        worksheet.column_dimensions[worksheet.cell(1, i+1).column_letter].width = max_length
                
                output.seek(0)
                
                file_name = f"detailed_product_data_{query}.xlsx" if is_detailed else f"shopping_results_{query}.xlsx"
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=file_name
                )
            
            # Normal search flow
            if not query:
                return jsonify({"error": "Query parameter is required"}), 400
                
            logger.info(f"Searching for: {query}")
            
            # Call the search function
            results = search_products(query)
            
            if not results:
                return jsonify({"message": "No results found. Please try a different search term."}), 404
                
            return jsonify({"results": results})
            
        else:
            # GET request - render search form
            return render_template('index.html', api_key=os.getenv("OXYLABS_API_KEY", ""))
            
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        return jsonify({"error": f"Error processing search: {str(e)}"}), 500

@app.route('/api/product/<product_id>', methods=['GET'])
def product_details_api(product_id):
    """
    Test endpoint to get details for a specific Amazon product by ASIN/product ID
    """
    try:
        logger.info(f"Received request for product ID: {product_id}")
        
        # Validate the product ID (ASIN)
        if not re.match(r'^[A-Z0-9]{10}$', product_id):
            logger.warning(f"Invalid product ID format: {product_id}")
            return jsonify({"error": "Invalid product ID format. Expected Amazon ASIN (10 characters alphanumeric)"}), 400
            
        product = get_product_details(product_id)
        
        if not product:
            logger.warning(f"Product not found: {product_id}")
            return jsonify({"error": "Product not found or failed to retrieve data"}), 404
            
        # Check for parse status code that indicates an error
        if isinstance(product, dict) and product.get('parse_status_code') == 12003:
            logger.warning(f"Product not found or unavailable: {product_id}")
            return jsonify({"error": "Product not found on Amazon or is currently unavailable", "details": product}), 404
            
        return jsonify({"product": product})
        
    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}")
        return jsonify({"error": f"Error getting product details: {str(e)}"}), 500

@app.route('/scrape-products', methods=['POST'])
def scrape_products():
    """Endpoint to scrape detailed product information for multiple products"""
    try:
        data = request.json
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({"error": "No product IDs provided"}), 400
        
        logger.info(f"Scraping details for {len(product_ids)} products")
        
        # Limit the number of products that can be scraped at once
        max_products = 10
        if len(product_ids) > max_products:
            logger.warning(f"Request for {len(product_ids)} products exceeded limit of {max_products}")
            product_ids = product_ids[:max_products]
        
        # Get details for each product
        results = []
        for product_id in product_ids:
            try:
                logger.info(f"Scraping product ID: {product_id}")
                product_details = get_product_details(product_id)
                
                # If we got valid results
                if product_details:
                    # Add the product ID to the results
                    product_details['productId'] = product_id
                    results.append(product_details)
                else:
                    # Add an error entry
                    results.append({
                        'productId': product_id,
                        'error': 'Failed to retrieve product details',
                        'title': f'Product {product_id}'
                    })
            except Exception as e:
                logger.error(f"Error scraping product {product_id}: {str(e)}")
                results.append({
                    'productId': product_id,
                    'error': f'Error: {str(e)}',
                    'title': f'Product {product_id}'
                })
        
        return jsonify({"results": results})
        
    except Exception as e:
        logger.error(f"Error processing batch scrape request: {str(e)}")
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

def get_product_details(product_id):
    """
    Get details for a specific Amazon product using Oxylabs API
    
    Args:
        product_id (str): Amazon ASIN/product ID
    """
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")
    
    logger.info(f"Getting details for product ID: {product_id}")
    
    # Structure payload for Oxylabs API
    payload = {
        'source': 'amazon',
        'domain': 'com',
        'url': f'https://www.amazon.com/dp/{product_id}',
        'parse': True
    }
    
    try:
        logger.info(f"Sending request to Oxylabs API for product: {product_id}")
        # Get response
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=(username, password),
            json=payload,
        )
        
        response.raise_for_status()
        logger.info(f"Response status code: {response.status_code}")
        
        results = response.json()
        logger.info(f"Response keys: {results.keys() if results else 'None'}")
        
        if not results or "results" not in results:
            logger.warning("No results found in API response")
            return None
            
        # Extract content from the response
        if not results["results"] or "content" not in results["results"][0]:
            logger.warning("No content in results")
            return None
        
        content = results["results"][0]["content"]
        logger.info(f"Product data retrieved successfully for ASIN: {product_id}")
        
        return content
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error occurred: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return None

if __name__ == '__main__':
    app.run(debug=True, port=5002) 