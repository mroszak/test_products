from flask import Flask, render_template, request, send_file, jsonify
from serpapi import GoogleSearch
import pandas as pd
import os
from dotenv import load_dotenv
import tempfile
import logging

app = Flask(__name__)
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_products(query):
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY")
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            logger.error(f"API Error: {results['error']}")
            return []
            
        if "shopping_results" not in results:
            logger.warning(f"No shopping results found for query: {query}")
            logger.debug(f"Full API response: {results}")
            return []
        
        return results["shopping_results"]
    except Exception as e:
        logger.error(f"Exception during search: {str(e)}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    if not query:
        return jsonify({"error": "Please enter a search term"}), 400
    
    logger.info(f"Searching for: {query}")
    results = search_products(query)
    
    if not results:
        return jsonify({"error": "No results found. Please try a different search term."}), 404
    
    # Create a temporary Excel file
    df = pd.DataFrame(results)
    temp_dir = tempfile.gettempdir()
    excel_path = os.path.join(temp_dir, f"shopping_results_{query}.xlsx")
    df.to_excel(excel_path, index=False)
    
    return send_file(
        excel_path,
        as_attachment=True,
        download_name=f"shopping_results_{query}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(debug=True, port=8080) 