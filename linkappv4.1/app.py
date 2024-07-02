import os
import logging
from flask import Flask, request, jsonify, render_template, send_file
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

def has_significant_content(soup, min_chars):
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        text = main_content.get_text(separator=' ', strip=True)
    else:
        text = soup.get_text(separator=' ', strip=True)
    return len(text) > min_chars

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_links', methods=['POST'])
def check_links():
    urls = request.form['urls'].split()
    min_chars = int(request.form['min_chars'])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    logger.info(f"Received request to check {len(urls)} URLs with minimum {min_chars} characters")

    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    for url in urls[:100]:  # Limit to first 100 URLs for safety
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            status_code = response.status_code
            if status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                has_content = has_significant_content(soup, min_chars)
            else:
                has_content = False
        except requests.RequestException as e:
            logger.error(f"Error checking URL {url}: {str(e)}")
            status_code = 'Error'
            has_content = False

        results.append({
            'URL': url,
            'Status Code': status_code,
            'Has Significant Content': 'Yes' if has_content else 'No'
        })

    df = pd.DataFrame(results)

    total_links = len(results)
    valid_links = sum(1 for r in results if r['Status Code'] == 200)
    invalid_links = total_links - valid_links
    links_without_content = sum(1 for r in results if r['Has Significant Content'] == 'No')

    summary = {
        'Total Links Analyzed': total_links,
        'Total Valid Links': valid_links,
        'Total Invalid Links': invalid_links,
        'Total Links Without Significant Content': links_without_content
    }

    df = pd.concat([pd.DataFrame([summary]), df], ignore_index=True)

    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8')
    output.seek(0)

    return jsonify({
        'summary': summary,
        'csv': output.getvalue().decode('utf-8')
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
