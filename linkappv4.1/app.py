import os
import logging
from flask import Flask, request, jsonify, render_template, send_file, Response
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = app.logger

def has_significant_content(soup):
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        text = main_content.get_text(separator=' ', strip=True)
    else:
        text = soup.get_text(separator=' ', strip=True)

    character_count = len(text)
    logger.info(f"Character count: {character_count}")
    return character_count > 300

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_links', methods=['POST'])
def check_links():
    urls = request.form['urls'].split()
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    logger.info(f"Received request to check {len(urls)} URLs")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    valid_count, invalid_count, insignificant_count = 0, 0, 0
    results = []
    for url in urls[:100]:  # Limit to first 100 URLs for safety
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url

        entry = {"URL": url}
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                if has_significant_content(soup):
                    entry["Content"] = "Significant"
                    valid_count += 1
                else:
                    entry["Content"] = "Insignificant"
                    insignificant_count += 1
                entry["Status"] = "Valid"
            else:
                entry["Status"] = f"Invalid ({response.status_code})"
                invalid_count += 1
        except requests.RequestException as e:
            entry["Status"] = f"Error ({str(e)})"
            invalid_count += 1
        
        results.append(entry)

    summary = {
        "total_urls": len(urls),
        "valid_links": valid_count,
        "invalid_links": invalid_count,
        "insignificant_content": insignificant_count
    }

    # Create CSV file
    df = pd.DataFrame(results)
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8')
    output.seek(0)

    # Choose what to return based on the request's accept header
    if 'text/csv' in request.headers.get('Accept', ''):
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name='links_analysis.csv'
        )
    else:
        return jsonify(summary)

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
