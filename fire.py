from flask import Flask, request, jsonify
import pandas as pd
import os
from datetime import datetime
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
from werkzeug.utils import secure_filename
from bank_statement_analyzer_module import BankStatementAnalyzer 

# Initialize Flask App
app = Flask(__name__)
CORS(app, origins=["http://localhost:4200","https://finance-app-weld-delta.vercel.app"])

# MongoDB Atlas Connection
MONGO_URI = "mongodb+srv://sanjaiad22:pass@finance-app.ukuqp.mongodb.net/?retryWrites=true&w=majority&appName=finance-app"
client = MongoClient(MONGO_URI)
db = client["finance_db"]

analyzer = BankStatementAnalyzer()

# Collections
expenses_collection = db["expenses"]
bill_reminders_collection = db["bill_reminders"]
expense_limits_collection = db["expense_limits"]

# Function to parse different date formats
def parse_date(date_str):
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Date format not recognized: {date_str}")

# Function to convert MongoDB documents to JSON serializable format
def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc
    
# Allowed File Extensions
ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def home():
    return jsonify({"message": "Bank Statement Analyzer API is running!"})

# 🟢 Upload PDF and Extract Transactions
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    # Validate File Type
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDFs are allowed."}), 400

    # Securely Save the File
    os.makedirs("uploads", exist_ok=True)
    pdf_path = os.path.join("uploads", secure_filename(file.filename))
    file.save(pdf_path)

    # Extract Transactions from PDF
    df = analyzer.extract_from_pdf(pdf_path)
    if df is None or df.empty:
        return jsonify({"error": "No transactions extracted from the PDF"}), 400

    # Save transactions in MongoDB
    transactions = df.to_dict(orient='records')
    print(df)
    if transactions:
        expenses_collection.insert_many(transactions)

    return jsonify({"message": "Transactions uploaded successfully", "file": file.filename}), 200

# 🟢 Manual Expense Entry
@app.route('/manual_entry', methods=['POST'])
def manual_entry():
    data = request.json
    required_fields = ['Date', 'Description', 'Type', 'Amount','Balance','Category']

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        data['date'] = parse_date(data['Date']).strftime("%d-%b-%Y")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    expenses_collection.insert_one(data)

    return jsonify({"message": "Transaction added successfully"})

# 🟢 Retrieve All Transactions
@app.route('/get_transactions', methods=['GET'])
def get_transactions():
    transactions = list(expenses_collection.find({}))
    return jsonify([serialize_doc(txn) for txn in transactions])

# 🟢 Delete a Transaction by ID
@app.route('/delete_transaction/<string:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    result = expenses_collection.delete_one({"_id": ObjectId(transaction_id)})

    if result.deleted_count == 0:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify({"message": "Transaction deleted successfully"})

# 🟢 Add Bill Reminder
@app.route('/add_bill_reminder', methods=['POST'])
def add_bill_reminder():
    data = request.json
    if "title" not in data or "date" not in data:
        return jsonify({"error": "Title and date are required"}), 400

    try:
        data["date"] = parse_date(data["date"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    bill_reminders_collection.insert_one(data)
    return jsonify({"message": "Bill reminder added successfully"})

# 🟢 Get Bill Reminders (Sorted by Date)
@app.route('/get_bill_reminders', methods=['GET'])
def get_bill_reminders():
    reminders = list(bill_reminders_collection.find().sort("date", ASCENDING))
    return jsonify([serialize_doc(reminder) for reminder in reminders])

# 🟢 Delete Bill Reminder
@app.route('/delete_bill_reminder/<string:reminder_id>', methods=['DELETE'])
def delete_bill_reminder(reminder_id):
    result = bill_reminders_collection.delete_one({"_id": ObjectId(reminder_id)})

    if result.deleted_count == 0:
        return jsonify({"error": "Bill reminder not found"}), 404

    return jsonify({"message": "Bill reminder deleted successfully"})

# 🟢 Set Monthly Expense Limit
@app.route('/set_expense_limit', methods=['POST'])
def set_expense_limit():
    data = request.json
    if "limit" not in data:
        return jsonify({"error": "Expense limit is required"}), 400

    current_month = datetime.now().strftime("%Y-%m")
    expense_limits_collection.update_one(
        {"month": current_month},
        {"$set": {"limit": data["limit"], "current_expense": 0}},
        upsert=True
    )

    return jsonify({"message": "Expense limit set successfully"})

# 🟢 Get Current Month's Expense Limit
@app.route('/get_expense_limit', methods=['GET'])
def get_expense_limit():
    current_month = datetime.now().strftime("%Y-%m")
    limit_data = expense_limits_collection.find_one({"month": current_month})

    if limit_data:
        return jsonify(serialize_doc(limit_data))
    else:
        return jsonify({"error": "No expense limit set for this month"}), 404

# 🟢 Update Current Month's Expense
@app.route('/update_expense', methods=['POST'])
def update_expense():
    data = request.json
    if "amount" not in data:
        return jsonify({"error": "Amount is required"}), 400

    current_month = datetime.now().strftime("%Y-%m")
    expense_limits_collection.update_one(
        {"month": current_month},
        {"$inc": {"current_expense": data["amount"]}},
        upsert=True
    )

    return jsonify({"message": "Expense updated successfully"})
    

# 🟢 Analyze Spending Patterns
@app.route('/analyze_spending', methods=['GET'])
def analyze_spending():
    transactions = list(expenses_collection.find({}, {'_id': 0}))

    if not transactions:
        return jsonify({"error": "No transactions available for analysis"}), 400

    analysis = analyzer.analyze_spending_patterns(transactions)
    return jsonify({"analysis": analysis}), 200


# 🟢 Generate Financial Suggestions
@app.route('/generate_suggestions', methods=['GET'])
def generate_suggestions():
    transactions = list(expenses_collection.find({}, {'_id': 0}))

    if not transactions:
        return jsonify({"error": "No transactions available for generating suggestions"}), 400

    analysis = analyzer.analyze_spending_patterns(transactions)
    suggestions = analyzer.generate_suggestions(analysis)

    return jsonify({"suggestions": suggestions}), 200



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

#if __name__ == '__main__':
    # from waitress import serve
    # serve(app, host='0.0.0.0', port=5000)
#    app.run(host='0.0.0.0', port=5000, debug=True)

