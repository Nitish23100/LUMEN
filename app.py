from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import ai_extractor
import database
import rag_engine

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
try:
    database.init_db()
    app.logger.info("Database initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize database: {e}")
    raise

# Initialize RAG engine
try:
    rag_engine.initialize_rag_engine()
    app.logger.info("RAG engine initialized successfully")
except Exception as e:
    app.logger.warning(f"Failed to initialize RAG engine: {e}")
    # Don't raise - RAG is optional functionality

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
            # Clean up uploaded file on file type error
            try:
                os.remove(file_path)
            except:
                pass
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
            # Clean up uploaded file on extraction failure
            try:
                os.remove(file_path)
            except:
                pass
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
            # Clean up uploaded file on database error
            try:
                os.remove(file_path)
            except:
                pass
            return jsonify({
                'success': False,
                'error': 'Failed to save transaction to database'
            }), 500
        
        # Add to vector database for semantic search
        try:
            rag_engine.add_transaction_to_vector_db(
                transaction_id=transaction_id,
                vendor=extracted_data.get('vendor', ''),
                category=extracted_data.get('category', ''),
                items_json=extracted_data.get('items', []),
                date=extracted_data.get('date', ''),
                amount=extracted_data.get('total', 0)
            )
            app.logger.info(f"Added transaction {transaction_id} to vector database")
        except Exception as e:
            app.logger.warning(f"Failed to add transaction {transaction_id} to vector database: {e}")
            # Don't fail the request if RAG fails
        
        # Clean up uploaded file after successful processing
        try:
            os.remove(file_path)
            app.logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as cleanup_error:
            app.logger.warning(f"Failed to clean up file {file_path}: {cleanup_error}")
        
        # Prepare response data
        response_data = extracted_data.copy()
        response_data['transaction_id'] = transaction_id
        response_data['original_filename'] = filename
        
        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'data': response_data
        })
        
    except Exception as e:
        # Clean up uploaded file on any unexpected error
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        
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

@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search page for semantic transaction search"""
    if request.method == 'GET':
        return render_template('search.html')
    
    try:
        # Get search query from form or JSON
        if request.is_json:
            data = request.get_json()
            query = data.get('query', '').strip()
            k = data.get('k', 10)
        else:
            query = request.form.get('query', '').strip()
            k = int(request.form.get('k', 10))
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Search query is required'
            }), 400
        
        # Search for similar transactions using RAG
        similar_transactions = rag_engine.get_similar_transactions(query, k)
        
        # Get full transaction details from database for each result
        detailed_results = []
        for similar_tx in similar_transactions:
            transaction_id = similar_tx.get('transaction_id')
            if transaction_id:
                # Get full transaction details
                full_transaction = database.get_transaction(transaction_id)
                if full_transaction:
                    # Combine RAG result with full transaction data
                    detailed_result = {
                        'id': full_transaction['id'],
                        'vendor': full_transaction['vendor'] or 'Unknown Vendor',
                        'date': full_transaction['date'] or 'Unknown Date',
                        'amount': full_transaction['amount'] or 0,
                        'category': full_transaction['category'] or 'other',
                        'subtotal': full_transaction['subtotal'] or 0,
                        'tax': full_transaction['tax'] or 0,
                        'payment_method': full_transaction['payment_method'] or 'unknown',
                        'confidence_score': full_transaction['confidence_score'] or 0,
                        'timestamp': full_transaction['timestamp'],
                        'items': full_transaction['items_json'] or [],
                        'flagged': full_transaction['flagged'] or 0,
                        'similarity_score': similar_tx.get('similarity_score', 0),
                        'description': similar_tx.get('description', '')
                    }
                    detailed_results.append(detailed_result)
        
        return jsonify({
            'success': True,
            'query': query,
            'results': detailed_results,
            'count': len(detailed_results)
        })
        
    except Exception as e:
        app.logger.error(f"Error processing search: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        }), 500

@app.route('/transaction/<int:transaction_id>')
def get_transaction(transaction_id):
    """API route to retrieve a single transaction as JSON"""
    try:
        # Retrieve transaction from database
        transaction = database.get_transaction(transaction_id)
        
        if not transaction:
            return jsonify({
                'success': False,
                'error': 'Transaction not found'
            }), 404
        
        # Convert transaction to dictionary and handle any None values
        transaction_data = {
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
            'flagged': transaction['flagged'] or 0,
            'raw_data': transaction['raw_data_json'] or {}
        }
        
        return jsonify({
            'success': True,
            'data': transaction_data
        })
        
    except Exception as e:
        app.logger.error(f"Error retrieving transaction {transaction_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error retrieving transaction: {str(e)}'
        }), 500

@app.route('/api/search', methods=['POST'])
def search_transactions():
    """API route to search for similar transactions using natural language"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query parameter is required'
            }), 400
        
        query = data['query']
        k = data.get('k', 5)  # Default to 5 results
        
        # Search for similar transactions
        similar_transactions = rag_engine.get_similar_transactions(query, k)
        
        return jsonify({
            'success': True,
            'query': query,
            'results': similar_transactions,
            'count': len(similar_transactions)
        })
        
    except Exception as e:
        app.logger.error(f"Error searching transactions: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        }), 500

@app.route('/api/context/<int:transaction_id>')
def get_transaction_context(transaction_id):
    """API route to get context for a transaction (similar past transactions)"""
    try:
        k = request.args.get('k', 5, type=int)
        
        # Get context for the transaction
        context = rag_engine.retrieve_context_for_transaction(transaction_id, k)
        
        if not context:
            return jsonify({
                'success': False,
                'error': 'Transaction not found or no context available'
            }), 404
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'context': context
        })
        
    except Exception as e:
        app.logger.error(f"Error getting transaction context: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to get context: {str(e)}'
        }), 500

@app.route('/api/rag/stats')
def get_rag_stats():
    """API route to get RAG engine statistics"""
    try:
        stats = rag_engine.get_collection_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        app.logger.error(f"Error getting RAG stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to get stats: {str(e)}'
        }), 500

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