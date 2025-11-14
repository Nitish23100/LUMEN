from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import ai_extractor
import database

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
database.initialize_database()

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Determine file type based on extension"""
    if not filename:
        return None
    
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    elif ext == 'pdf':
        return 'pdf'
    elif ext == 'txt':
        return 'text'
    else:
        return None

@app.route('/')
def home():
    """Homepage route"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload route for handling file uploads and AI extraction"""
    if request.method == 'GET':
        return render_template('upload.html')
    
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Check if file type is allowed
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'File type not supported. Please upload JPG, PNG, PDF, or TXT files.'
            }), 400
        
        # Secure the filename and save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = timestamp + filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(file_path)
        
        # Detect file type
        file_type = get_file_type(filename)
        if not file_type:
            return jsonify({
                'success': False,
                'error': 'Unable to determine file type'
            }), 400
        
        # Extract data using appropriate AI function
        extracted_data = None
        
        if file_type == 'image':
            extracted_data = ai_extractor.extract_from_image(file_path)
        elif file_type == 'pdf':
            extracted_data = ai_extractor.extract_from_pdf(file_path)
        elif file_type == 'text':
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            extracted_data = ai_extractor.extract_from_text(text_content)
        
        # Check if extraction was successful
        if not extracted_data:
            return jsonify({
                'success': False,
                'error': 'Failed to extract data from file. Please try a different file or check if it contains receipt/invoice information.'
            }), 400
        
        # Prepare data for database
        transaction_data = {
            'vendor': extracted_data.get('vendor', ''),
            'date': extracted_data.get('date', ''),
            'amount': extracted_data.get('total', 0),
            'category': extracted_data.get('category', 'other'),
            'items_json': extracted_data.get('items', []),
            'subtotal': extracted_data.get('subtotal', 0),
            'tax': extracted_data.get('tax', 0),
            'payment_method': extracted_data.get('payment_method', 'unknown'),
            'raw_data_json': extracted_data,
            'confidence_score': extracted_data.get('confidence_score', 0),
            'flagged': 0
        }
        
        # Save to database
        transaction_id = database.save_transaction(transaction_data)
        
        if not transaction_id:
            return jsonify({
                'success': False,
                'error': 'Failed to save transaction to database'
            }), 500
        
        # Prepare response data
        response_data = extracted_data.copy()
        response_data['transaction_id'] = transaction_id
        response_data['file_path'] = file_path
        response_data['original_filename'] = filename
        
        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'data': response_data
        })
        
    except Exception as e:
        app.logger.error(f"Error processing upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'An error occurred while processing the file: {str(e)}'
        }), 500

@app.route('/preview/<int:transaction_id>')
def preview_transaction(transaction_id):
    """Preview route to display transaction data in a nice card format"""
    try:
        # Retrieve transaction from database
        transaction = database.get_transaction(transaction_id)
        
        if not transaction:
            flash('Transaction not found', 'error')
            return redirect(url_for('home'))
        
        # Format the data for display
        formatted_transaction = {
            'id': transaction['id'],
            'vendor': transaction['vendor'] or 'Unknown Vendor',
            'date': transaction['date'] or 'Unknown Date',
            'amount': transaction['amount'] or 0,
            'category': transaction['category'] or 'other',
            'subtotal': transaction['subtotal'] or 0,
            'tax': transaction['tax'] or 0,
            'payment_method': transaction['payment_method'] or 'unknown',
            'confidence_score': transaction['confidence_score'] or 0,
            'timestamp': transaction['timestamp'],
            'items': transaction['items_json'] or [],
            'flagged': transaction['flagged']
        }
        
        return render_template('preview.html', transaction=formatted_transaction)
        
    except Exception as e:
        app.logger.error(f"Error retrieving transaction {transaction_id}: {str(e)}")
        flash('Error retrieving transaction', 'error')
        return redirect(url_for('home'))

@app.route('/transactions')
def transactions():
    """Route to display all transactions"""
    try:
        all_transactions = database.get_all_transactions()
        return render_template('transactions.html', transactions=all_transactions)
    except Exception as e:
        app.logger.error(f"Error retrieving transactions: {str(e)}")
        flash('Error retrieving transactions', 'error')
        return redirect(url_for('home'))

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    return jsonify({
        'success': False,
        'error': 'File too large. Maximum size is 16MB.'
    }), 413

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)