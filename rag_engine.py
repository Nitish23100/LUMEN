import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGEngine:
    """RAG Engine for semantic search of financial transactions using ChromaDB"""
    
    def __init__(self, db_path: str = "chroma_db"):
        """
        Initialize the RAG engine with ChromaDB and sentence transformer model.
        
        Args:
            db_path: Path to store ChromaDB data
        """
        self.db_path = db_path
        self.collection_name = "financial_transactions"
        self.model_name = "all-MiniLM-L6-v2"
        
        # Initialize components
        self.client = None
        self.collection = None
        self.embedding_model = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize ChromaDB client, collection, and embedding model"""
        try:
            # Initialize ChromaDB persistent client
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create or get collection with cosine similarity
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            # Initialize sentence transformer model
            logger.info(f"Loading embedding model: {self.model_name}")
            self.embedding_model = SentenceTransformer(self.model_name)
            
            logger.info("RAG Engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG Engine: {e}")
            raise
    
    def _create_transaction_text(self, vendor: str, category: str, items_json: List[Dict], 
                                date: str, amount: float) -> str:
        """
        Create descriptive text from transaction data for embedding.
        
        Args:
            vendor: Store/vendor name
            category: Transaction category
            items_json: List of items purchased
            date: Transaction date
            amount: Total amount
            
        Returns:
            Descriptive text for embedding
        """
        try:
            # Format items list
            items_text = ""
            if items_json and isinstance(items_json, list):
                item_names = []
                for item in items_json:
                    if isinstance(item, dict) and 'name' in item:
                        name = item['name']
                        price = item.get('price', 0)
                        item_names.append(f"{name} (${price:.2f})")
                
                if item_names:
                    items_text = f"Items: {', '.join(item_names[:10])}"  # Limit to 10 items
                    if len(items_json) > 10:
                        items_text += f" and {len(items_json) - 10} more items"
            
            # Create descriptive text
            base_text = f"Transaction at {vendor or 'unknown store'} on {date or 'unknown date'} for {category or 'general'} spending ${amount:.2f}"
            
            if items_text:
                full_text = f"{base_text}. {items_text}"
            else:
                full_text = base_text
            
            return full_text
            
        except Exception as e:
            logger.error(f"Error creating transaction text: {e}")
            return f"Transaction at {vendor or 'unknown'} for ${amount:.2f}"
    
    def add_transaction_to_vector_db(self, transaction_id: int, vendor: str, category: str, 
                                   items_json: List[Dict], date: str, amount: float) -> bool:
        """
        Add a transaction to the vector database.
        
        Args:
            transaction_id: Unique transaction ID
            vendor: Store/vendor name
            category: Transaction category
            items_json: List of items purchased
            date: Transaction date
            amount: Total amount
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create descriptive text
            transaction_text = self._create_transaction_text(vendor, category, items_json, date, amount)
            
            # Create embedding
            embedding = self.embedding_model.encode([transaction_text])[0].tolist()
            
            # Prepare metadata
            metadata = {
                "transaction_id": transaction_id,
                "vendor": vendor or "unknown",
                "category": category or "other",
                "date": date or "unknown",
                "amount": float(amount) if amount else 0.0,
                "item_count": len(items_json) if items_json else 0
            }
            
            # Add to ChromaDB collection
            self.collection.add(
                embeddings=[embedding],
                documents=[transaction_text],
                metadatas=[metadata],
                ids=[f"transaction_{transaction_id}"]
            )
            
            logger.info(f"Added transaction {transaction_id} to vector database")
            return True
            
        except Exception as e:
            logger.error(f"Error adding transaction {transaction_id} to vector database: {e}")
            return False
    
    def get_similar_transactions(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar transactions based on natural language query.
        
        Args:
            query: Natural language query
            k: Number of similar transactions to return
            
        Returns:
            List of similar transactions with metadata and similarity scores
        """
        try:
            if not query.strip():
                logger.warning("Empty query provided")
                return []
            
            # Create embedding for query
            query_embedding = self.embedding_model.encode([query])[0].tolist()
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, 100),  # Limit to reasonable number
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            similar_transactions = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    similarity_score = 1 - distance  # Convert distance to similarity
                    
                    similar_transactions.append({
                        'transaction_id': metadata.get('transaction_id'),
                        'vendor': metadata.get('vendor'),
                        'category': metadata.get('category'),
                        'date': metadata.get('date'),
                        'amount': metadata.get('amount'),
                        'item_count': metadata.get('item_count', 0),
                        'description': doc,
                        'similarity_score': round(similarity_score, 3)
                    })
            
            logger.info(f"Found {len(similar_transactions)} similar transactions for query: '{query[:50]}...'")
            return similar_transactions
            
        except Exception as e:
            logger.error(f"Error searching for similar transactions: {e}")
            return []
    
    def retrieve_context_for_transaction(self, transaction_id: int, k: int = 5) -> Dict[str, Any]:
        """
        Get context for a transaction by finding similar past transactions.
        
        Args:
            transaction_id: ID of the transaction to get context for
            k: Number of similar transactions to return as context
            
        Returns:
            Dictionary with transaction details and similar transactions
        """
        try:
            # Get transaction details from database
            transaction = database.get_transaction(transaction_id)
            if not transaction:
                logger.error(f"Transaction {transaction_id} not found in database")
                return {}
            
            # Create query from transaction details
            query = self._create_transaction_text(
                vendor=transaction.get('vendor', ''),
                category=transaction.get('category', ''),
                items_json=transaction.get('items_json', []),
                date=transaction.get('date', ''),
                amount=transaction.get('amount', 0)
            )
            
            # Find similar transactions (excluding the current one)
            similar_transactions = self.get_similar_transactions(query, k + 1)
            
            # Filter out the current transaction
            context_transactions = [
                t for t in similar_transactions 
                if t['transaction_id'] != transaction_id
            ][:k]
            
            # Prepare context
            context = {
                'current_transaction': {
                    'id': transaction['id'],
                    'vendor': transaction.get('vendor'),
                    'category': transaction.get('category'),
                    'date': transaction.get('date'),
                    'amount': transaction.get('amount'),
                    'items': transaction.get('items_json', [])
                },
                'similar_transactions': context_transactions,
                'context_summary': self._generate_context_summary(context_transactions)
            }
            
            logger.info(f"Retrieved context for transaction {transaction_id} with {len(context_transactions)} similar transactions")
            return context
            
        except Exception as e:
            logger.error(f"Error retrieving context for transaction {transaction_id}: {e}")
            return {}
    
    def _generate_context_summary(self, similar_transactions: List[Dict[str, Any]]) -> str:
        """
        Generate a summary of similar transactions for context.
        
        Args:
            similar_transactions: List of similar transactions
            
        Returns:
            Summary text
        """
        if not similar_transactions:
            return "No similar transactions found."
        
        # Analyze patterns
        vendors = [t['vendor'] for t in similar_transactions if t['vendor']]
        categories = [t['category'] for t in similar_transactions if t['category']]
        amounts = [t['amount'] for t in similar_transactions if t['amount']]
        
        summary_parts = []
        
        # Most common vendor
        if vendors:
            most_common_vendor = max(set(vendors), key=vendors.count)
            vendor_count = vendors.count(most_common_vendor)
            if vendor_count > 1:
                summary_parts.append(f"You frequently shop at {most_common_vendor} ({vendor_count} times)")
        
        # Category analysis
        if categories:
            most_common_category = max(set(categories), key=categories.count)
            summary_parts.append(f"Most similar transactions are in {most_common_category}")
        
        # Amount analysis
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            summary_parts.append(f"Average amount for similar transactions: ${avg_amount:.2f}")
        
        return ". ".join(summary_parts) if summary_parts else "Similar transaction patterns found."
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector database collection.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()
            
            # Get sample of transactions for analysis
            if count > 0:
                sample_results = self.collection.get(
                    limit=min(100, count),
                    include=["metadatas"]
                )
                
                if sample_results['metadatas']:
                    categories = [m.get('category') for m in sample_results['metadatas'] if m.get('category')]
                    vendors = [m.get('vendor') for m in sample_results['metadatas'] if m.get('vendor')]
                    amounts = [m.get('amount') for m in sample_results['metadatas'] if m.get('amount')]
                    
                    stats = {
                        'total_transactions': count,
                        'unique_categories': len(set(categories)) if categories else 0,
                        'unique_vendors': len(set(vendors)) if vendors else 0,
                        'avg_amount': round(sum(amounts) / len(amounts), 2) if amounts else 0,
                        'collection_name': self.collection_name,
                        'embedding_model': self.model_name
                    }
                else:
                    stats = {
                        'total_transactions': count,
                        'collection_name': self.collection_name,
                        'embedding_model': self.model_name
                    }
            else:
                stats = {
                    'total_transactions': 0,
                    'collection_name': self.collection_name,
                    'embedding_model': self.model_name
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {'error': str(e)}

# Global RAG engine instance
rag_engine = None

def initialize_rag_engine():
    """Initialize the global RAG engine instance"""
    global rag_engine
    try:
        rag_engine = RAGEngine()
        logger.info("Global RAG engine initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize global RAG engine: {e}")
        return False

def add_transaction_to_vector_db(transaction_id: int, vendor: str, category: str, 
                               items_json: List[Dict], date: str, amount: float) -> bool:
    """
    Convenience function to add transaction to vector database.
    
    Args:
        transaction_id: Unique transaction ID
        vendor: Store/vendor name
        category: Transaction category
        items_json: List of items purchased
        date: Transaction date
        amount: Total amount
        
    Returns:
        True if successful, False otherwise
    """
    global rag_engine
    if not rag_engine:
        logger.warning("RAG engine not initialized, attempting to initialize...")
        if not initialize_rag_engine():
            return False
    
    return rag_engine.add_transaction_to_vector_db(transaction_id, vendor, category, items_json, date, amount)

def get_similar_transactions(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Convenience function to find similar transactions.
    
    Args:
        query: Natural language query
        k: Number of similar transactions to return
        
    Returns:
        List of similar transactions with metadata and similarity scores
    """
    global rag_engine
    if not rag_engine:
        logger.warning("RAG engine not initialized")
        return []
    
    return rag_engine.get_similar_transactions(query, k)

def retrieve_context_for_transaction(transaction_id: int, k: int = 5) -> Dict[str, Any]:
    """
    Convenience function to get context for a transaction.
    
    Args:
        transaction_id: ID of the transaction to get context for
        k: Number of similar transactions to return as context
        
    Returns:
        Dictionary with transaction details and similar transactions
    """
    global rag_engine
    if not rag_engine:
        logger.warning("RAG engine not initialized")
        return {}
    
    return rag_engine.retrieve_context_for_transaction(transaction_id, k)

def get_collection_stats() -> Dict[str, Any]:
    """
    Convenience function to get collection statistics.
    
    Returns:
        Dictionary with collection statistics
    """
    global rag_engine
    if not rag_engine:
        logger.warning("RAG engine not initialized")
        return {}
    
    return rag_engine.get_collection_stats()

# Test function
def test_rag_engine():
    """Test the RAG engine functionality"""
    print("Testing RAG Engine...")
    print("=" * 50)
    
    try:
        # Initialize
        if initialize_rag_engine():
            print("✓ RAG Engine initialized successfully")
        else:
            print("✗ RAG Engine initialization failed")
            return
        
        # Test adding a transaction
        success = add_transaction_to_vector_db(
            transaction_id=999,
            vendor="Test Store",
            category="groceries",
            items_json=[{"name": "Milk", "price": 3.99}, {"name": "Bread", "price": 2.49}],
            date="2024-01-15",
            amount=6.48
        )
        
        if success:
            print("✓ Test transaction added to vector database")
        else:
            print("✗ Failed to add test transaction")
        
        # Test similarity search
        similar = get_similar_transactions("grocery shopping for milk and bread", k=3)
        print(f"✓ Found {len(similar)} similar transactions")
        
        # Test stats
        stats = get_collection_stats()
        print(f"✓ Collection stats: {stats.get('total_transactions', 0)} transactions")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("=" * 50)

if __name__ == "__main__":
    test_rag_engine()