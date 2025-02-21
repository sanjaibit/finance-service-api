from flask import Flask, request, jsonify
import pandas as pd
import os
from datetime import datetime
from bank_statement_analyzer_module import BankStatementAnalyzer, process_manual_entry

app = Flask(__name__)
analyzer = BankStatementAnalyzer()

def parse_date(date_str):
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Date format not recognized: {date_str}")

@app.route('/')
def home():
    return "Bank Statement Analyzer API is running!"

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        print(request.files)
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    os.makedirs("uploads", exist_ok=True)
    pdf_path = os.path.join("uploads", file.filename)
    file.save(pdf_path)
    
    df = analyzer.extract_from_pdf(pdf_path)
    if df.empty:
        return jsonify({"error": "No transactions extracted from the PDF"}), 400
    
    analysis = analyzer.analyze_spending_patterns(df)
    suggestions = analyzer.generate_suggestions(analysis)
    
    return jsonify({
        "transactions": df.to_dict(orient='records'),
        "analysis": analysis,
        "suggestions": suggestions
    })

@app.route('/manual_entry', methods=['POST'])
def manual_entry():
    data = request.json
    required_fields = ['date', 'description', 'amount', 'transaction_type']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        data['date'] = parse_date(data['date'])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    result = process_manual_entry(
        data['date'].strftime("%d-%b-%Y"), data['description'], data['amount'], data['transaction_type']
    )
    return jsonify(result)

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
