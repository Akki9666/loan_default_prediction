from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import csv
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# MongoDB connection
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['loan_default_prediction']
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('sign_in'))
        return f(*args, **kwargs)
    return decorated_function

# Prediction Logic
def calculate_prediction(loan_details):
    # Extract loan data
    loan_amount = float(loan_details['loan_amount'])
    annual_interest_rate = float(loan_details['annual_interest_rate'])
    loan_tenure_years = int(loan_details['loan_tenure_years'])
    credit_score = int(loan_details['credit_score'])
    
    # Calculate EMI
    rate = annual_interest_rate / (12 * 100)  # Monthly interest rate
    tenure = loan_tenure_years * 12  # Tenure in months
    emi = (loan_amount * rate * (1 + rate)**tenure) / ((1 + rate)**tenure - 1)

    # Simple risk assessment
    risk_score = 0
    risk_score += 1 if credit_score < 700 else 0
    risk_score += 1 if loan_amount > 1000000 else 0
    risk_score += 1 if annual_interest_rate > 12 else 0

    default_risk = "High" if risk_score >= 2 else "Medium" if risk_score == 1 else "Low"
    
    return round(emi, 2), default_risk

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            flash('Successfully logged in.', 'success')
            return redirect(url_for('details'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('sign_in.html')

@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Input validation
        if not all([name, email, gender, dob, phone, password, confirm_password]):
            flash('All fields are required.', 'error')
            return redirect(url_for('sign_up'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('sign_up'))
        
        if db.users.find_one({'email': email}):
            flash('Email already registered.', 'error')
            return redirect(url_for('sign_up'))

        # Create new user
        user = {
            'name': name,
            'email': email,
            'gender': gender,
            'dob': dob,
            'phone': phone,
            'password': generate_password_hash(password),
            'created_at': datetime.utcnow()
        }
        
        try:
            db.users.insert_one(user)
            flash('Registration successful! Please sign in.', 'success')
            return redirect(url_for('sign_in'))
        except Exception as e:
            flash(f'Error during registration: {e}', 'error')
    
    return render_template('sign_up.html')

@app.route('/details', methods=['GET', 'POST'])
@login_required
def details():
    if request.method == 'POST':
        loan_details = {
            'loan_amount': request.form.get('loan_amount'),
            'annual_interest_rate': request.form.get('annual_interest_rate'),
            'loan_tenure_years': request.form.get('loan_tenure_years'),
            'credit_score': request.form.get('credit_score'),
            'user_id': session['user_id'],
            'created_at': datetime.utcnow()
        }

        # Validate input
        if not all(loan_details.values()):
            flash('All fields are required.', 'error')
            return redirect(url_for('details'))
        
        try:
            # Save the details in the database
            db.loan_applications.insert_one(loan_details)

            # Calculate prediction
            emi, default_risk = calculate_prediction(loan_details)

            # Pass data to prediction page
            return render_template('prediction.html', loan_details=loan_details, emi=emi, default_risk=default_risk)
        except Exception as e:
            flash(f'Error submitting loan application: {e}', 'error')
    
    return render_template('details.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
