import pandas as pd
import re
from datetime import datetime
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import joblib

class BankStatementAnalyzer:
    def __init__(self):
        self.categories = {
            'FOOD': ['SWIGGY', 'ZOMATO', 'RESTAURANT', 'HOTEL'],
            'TRANSPORT': ['UBER', 'OLA', 'METRO', 'FUEL', 'PETROL'],
            'SHOPPING': ['AMAZON', 'FLIPKART', 'MYNTRA', 'RETAIL'],
            'UTILITIES': ['ELECTRICITY', 'WATER', 'GAS', 'MOBILE', 'INTERNET'],
            'ENTERTAINMENT': ['NETFLIX', 'PRIME', 'HOTSTAR', 'MOVIE'],
            'TRANSFER': ['UPI', 'NEFT', 'IMPS', 'TRANSFER']
        }
        
        self.vectorizer = TfidfVectorizer()
        self.classifier = RandomForestClassifier()
    
    def extract_from_pdf(self, pdf_path):
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return pd.DataFrame()
            
        return self.parse_text_to_dataframe(text)

    def parse_text_to_dataframe(self, text):
        lines = text.split("\n")
        transactions = []

        for i, line in enumerate(lines):
            #print(f"Line {i}: {line}")  # Debugging each line
            
            parts = line.split()
            if len(parts) < 5:  # Skip invalid lines
                continue

            try:
                date = datetime.strptime(parts[0], "%d-%b-%Y")  # Extract date
                
                transfer_index = parts.index("Transfer")

                description = " ".join(parts[1:transfer_index])

                # Handling separate '-' before amount
                #if parts[transfer_index + 1] == "-":
                #   amount = float("-" + parts[transfer_index + 2])  # Merge '-' with the number
                #   balance = float(parts[transfer_index + 3])  # Balance is the next number
                    
                if parts[transfer_index + 2] == "-":
                    amount = float(parts[transfer_index + 1])  # Merge '-' with the number
                    balance = float(parts[transfer_index + 3])  # Balance is the next number
                

                trans_type = "DR" if amount > 0 else "CR"
                amount = abs(amount)  
                
                transactions.append({
                    "Date": date,
                    "Description": description,
                    "Type": trans_type,
                    "Amount": amount,
                    "Balance": balance
                })

            except Exception as e:
                pass


        return pd.DataFrame(transactions)

    def train_classifier(self, df):
        if df.empty or 'Category' not in df:
            print("Training data missing categories!")
            return
        
        X = self.vectorizer.fit_transform(df['Description'])
        y = df['Category']
        
        self.classifier.fit(X, y)
        joblib.dump(self.classifier, 'transaction_classifier.pkl')
        joblib.dump(self.vectorizer, 'vectorizer.pkl')

    def classify_transaction(self, description):
        description = description.upper()

        try:
            self.classifier = joblib.load('transaction_classifier.pkl')
            self.vectorizer = joblib.load('vectorizer.pkl')
            vec_desc = self.vectorizer.transform([description])
            return self.classifier.predict(vec_desc)[0]
        except:
            for category, keywords in self.categories.items():
                if any(keyword in description for keyword in keywords):
                    return category
            return 'OTHERS'

    def analyze_spending_patterns(self, df):
        df['Category'] = df['Description'].apply(self.classify_transaction)
        filtered_df = df[df['Amount'] >= 50]
        
        analysis = {
            'category_totals': df.groupby('Category')['Amount'].sum().to_dict(),
            'monthly_spending': df.groupby(df['Date'].dt.strftime('%Y-%m'))['Amount'].sum().to_dict(),
            'largest_transactions': filtered_df.nlargest(5, 'Amount')[['Date', 'Description', 'Amount', 'Category']].to_dict('records')
        }
        
        return analysis
    
    def generate_suggestions(self, analysis):
        suggestions = []
        category_spending = {k: abs(v) for k, v in analysis['category_totals'].items()}
        total_spend = sum(category_spending.values())

        if total_spend > 0:
            for category, amount in category_spending.items():
                percentage = (amount / total_spend) * 100

                if category == 'FOOD' and percentage > 30:
                    suggestions.append(f"Your food expenses ({percentage:.1f}%) are high. Consider meal planning.")

                elif category == 'ENTERTAINMENT' and percentage > 15:
                    suggestions.append(f"Your entertainment spending ({percentage:.1f}%) could be optimized.")

                elif category == 'SHOPPING' and percentage > 25:
                    suggestions.append(f"Your shopping expenses ({percentage:.1f}%) are significant.")

        if analysis['largest_transactions']:
            suggestions.append("Notable large transactions detected. Review your expenses.")

        return suggestions

def process_manual_entry(date, description, amount, transaction_type):
    analyzer = BankStatementAnalyzer()
    df = pd.DataFrame({
        'Date': [datetime.strptime(date, '%d-%b-%Y')],
        'Description': [description],
        'Type': [transaction_type],
        'Amount': [float(amount)],
        'Balance': [0]  # Optional balance tracking
    })
    
    analysis = analyzer.analyze_spending_patterns(df)
    suggestions = analyzer.generate_suggestions(analysis)
    
    return {
        'classification': analyzer.classify_transaction(description),
        'analysis': analysis,
        'suggestions': suggestions
    }

# Example Usage
if __name__ == "__main__":
    analyzer = BankStatementAnalyzer()
    
    df = analyzer.extract_from_pdf("1202202520021000_955507[1].pdf")
    if not df.empty:
        #print("\nParsed Transactions:\n")
        #print(df.to_string(index=False))  
        
        analysis = analyzer.analyze_spending_patterns(df)
        suggestions = analyzer.generate_suggestions(analysis)
        df_category_totals = pd.DataFrame(list(analysis['category_totals'].items()), columns=['Category', 'Total Amount'])

        df_monthly_spending = pd.DataFrame(list(analysis['monthly_spending'].items()), columns=['Month', 'Total Spending'])

        df_largest_transactions = pd.DataFrame(analysis['largest_transactions'])

        print("\nCategory Totals:\n", df_category_totals.to_string(index=False))
        print("\nMonthly Spending:\n", df_monthly_spending.to_string(index=False))
        print("\nLargest Transactions:\n", df_largest_transactions.to_string(index=False))

        print("\nSuggestions:")
        for suggestion in suggestions:
            print(f"- {suggestion}")

    else:
        print("No pdf")
   