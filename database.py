import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any

DATABASE_PATH = 'lumen.db'

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database and create tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT 1,
                vendor TEXT,
                date TEXT,
                amount REAL,
                category TEXT,
                items_json TEXT,
                subtotal REAL,
                tax REAL,
                payment_method TEXT,
                raw_data_json TEXT,
                confidence_score INTEGER,
                flagged BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("Database initialized successfully")

def save_transaction(data: Dict[str, Any]) -> int:
    """
    Insert a new transaction into the database.
    
    Args:
        data: Dictionary containing transaction data
        
    Returns:
        int: The ID of the inserted transaction
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Convert items and raw_data to JSON strings if they're not already
        items_json = data.get('items_json')
        if isinstance(items_json, (dict, list)):
            items_json = json.dumps(items_json)
            
        raw_data_json = data.get('raw_data_json')
        if isinstance(raw_data_json, (dict, list)):
            raw_data_json = json.dumps(raw_data_json)
        
        cursor.execute('''
            INSERT INTO transactions (
                user_id, vendor, date, amount, category, items_json,
                subtotal, tax, payment_method, raw_data_json,
                confidence_score, flagged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('user_id', 1),
            data.get('vendor'),
            data.get('date'),
            data.get('amount'),
            data.get('category'),
            items_json,
            data.get('subtotal'),
            data.get('tax'),
            data.get('payment_method'),
            raw_data_json,
            data.get('confidence_score'),
            data.get('flagged', 0)
        ))
        
        transaction_id = cursor.lastrowid
        conn.commit()
        
        return transaction_id

def get_transaction(transaction_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single transaction by ID.
    
    Args:
        transaction_id: The ID of the transaction to retrieve
        
    Returns:
        Dict containing transaction data or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
        row = cursor.fetchone()
        
        if row:
            transaction = dict(row)
            
            # Parse JSON fields back to Python objects
            if transaction['items_json']:
                try:
                    transaction['items_json'] = json.loads(transaction['items_json'])
                except json.JSONDecodeError:
                    pass
                    
            if transaction['raw_data_json']:
                try:
                    transaction['raw_data_json'] = json.loads(transaction['raw_data_json'])
                except json.JSONDecodeError:
                    pass
                    
            return transaction
        
        return None

def get_all_transactions() -> List[Dict[str, Any]]:
    """
    Retrieve all transactions from the database.
    
    Returns:
        List of dictionaries containing transaction data
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions ORDER BY timestamp DESC')
        rows = cursor.fetchall()
        
        transactions = []
        for row in rows:
            transaction = dict(row)
            
            # Parse JSON fields back to Python objects
            if transaction['items_json']:
                try:
                    transaction['items_json'] = json.loads(transaction['items_json'])
                except json.JSONDecodeError:
                    pass
                    
            if transaction['raw_data_json']:
                try:
                    transaction['raw_data_json'] = json.loads(transaction['raw_data_json'])
                except json.JSONDecodeError:
                    pass
                    
            transactions.append(transaction)
        
        return transactions

def get_transactions_by_user(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all transactions for a specific user.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        List of dictionaries containing transaction data
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
        rows = cursor.fetchall()
        
        transactions = []
        for row in rows:
            transaction = dict(row)
            
            # Parse JSON fields back to Python objects
            if transaction['items_json']:
                try:
                    transaction['items_json'] = json.loads(transaction['items_json'])
                except json.JSONDecodeError:
                    pass
                    
            if transaction['raw_data_json']:
                try:
                    transaction['raw_data_json'] = json.loads(transaction['raw_data_json'])
                except json.JSONDecodeError:
                    pass
                    
            transactions.append(transaction)
        
        return transactions

def update_transaction(transaction_id: int, data: Dict[str, Any]) -> bool:
    """
    Update an existing transaction.
    
    Args:
        transaction_id: The ID of the transaction to update
        data: Dictionary containing updated transaction data
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Convert items and raw_data to JSON strings if they're not already
        items_json = data.get('items_json')
        if isinstance(items_json, (dict, list)):
            items_json = json.dumps(items_json)
            
        raw_data_json = data.get('raw_data_json')
        if isinstance(raw_data_json, (dict, list)):
            raw_data_json = json.dumps(raw_data_json)
        
        cursor.execute('''
            UPDATE transactions SET
                user_id = ?, vendor = ?, date = ?, amount = ?, category = ?,
                items_json = ?, subtotal = ?, tax = ?, payment_method = ?,
                raw_data_json = ?, confidence_score = ?, flagged = ?
            WHERE id = ?
        ''', (
            data.get('user_id', 1),
            data.get('vendor'),
            data.get('date'),
            data.get('amount'),
            data.get('category'),
            items_json,
            data.get('subtotal'),
            data.get('tax'),
            data.get('payment_method'),
            raw_data_json,
            data.get('confidence_score'),
            data.get('flagged', 0),
            transaction_id
        ))
        
        success = cursor.rowcount > 0
        conn.commit()
        
        return success

def delete_transaction(transaction_id: int) -> bool:
    """
    Delete a transaction by ID.
    
    Args:
        transaction_id: The ID of the transaction to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        success = cursor.rowcount > 0
        conn.commit()
        
        return success

def initialize_database():
    """Initialize the database when the app starts."""
    try:
        init_db()
        print("Database connection established and tables created")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    # Test the database setup
    initialize_database()
    
    # Test data
    test_transaction = {
        'vendor': 'Test Store',
        'date': '2024-01-15',
        'amount': 25.99,
        'category': 'Groceries',
        'items_json': [{'name': 'Milk', 'price': 3.99}, {'name': 'Bread', 'price': 2.50}],
        'subtotal': 23.99,
        'tax': 2.00,
        'payment_method': 'Credit Card',
        'raw_data_json': {'ocr_text': 'Sample receipt text'},
        'confidence_score': 85
    }
    
    # Test saving and retrieving
    transaction_id = save_transaction(test_transaction)
    print(f"Saved transaction with ID: {transaction_id}")
    
    retrieved = get_transaction(transaction_id)
    print(f"Retrieved transaction: {retrieved}")
    
    all_transactions = get_all_transactions()
    print(f"Total transactions: {len(all_transactions)}")