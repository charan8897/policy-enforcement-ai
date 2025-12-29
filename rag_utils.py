#!/usr/bin/env python3
"""RAG utilities for policy enforcement system"""

import chromadb
from pathlib import Path

class RAGManager:
    """Manage RAG vector database operations"""
    
    def __init__(self, db_path="./chroma_db", db_name="policies"):
        self.db_path = db_path
        self.db_name = db_name
        self.client = chromadb.PersistentClient(path=db_path)
        try:
            self.collection = self.client.get_collection(name=db_name)
        except Exception as e:
            raise Exception(f"Vector DB not found: {e}")
    
    def search(self, query, limit=5):
        """Search for relevant policy sections"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit
            )
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            return []
    
    def get_context(self, query, limit=3, join_char="\n\n"):
        """Get combined context for LLM prompt"""
        docs = self.search(query, limit)
        return join_char.join(docs)
    
    def list_policies(self):
        """List all policies in database"""
        results = self.collection.get(limit=10000)
        sources = set()
        source_chunks = {}
        
        for i, meta in enumerate(results['metadatas']):
            source = meta.get('source', 'unknown')
            sources.add(source)
            if source not in source_chunks:
                source_chunks[source] = 0
            source_chunks[source] += 1
        
        return source_chunks
    
    def get_stats(self):
        """Get database statistics"""
        results = self.collection.get(limit=10000)
        sources = self.list_policies()
        
        return {
            'total_chunks': len(results['ids']),
            'policies': sources,
            'collection': self.db_name,
            'path': self.db_path
        }
    
    def clear_policy(self, policy_name):
        """Remove all chunks from a specific policy"""
        results = self.collection.get(limit=10000)
        ids_to_delete = []
        
        for i, meta in enumerate(results['metadatas']):
            if policy_name in meta.get('source', ''):
                ids_to_delete.append(results['ids'][i])
        
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
            return len(ids_to_delete)
        return 0
    
    def add_document(self, text, source, chunk_size=1000, overlap=100):
        """Add a new document to the database"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # Split text
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = splitter.split_text(text)
        
        # Create IDs
        policy_name = Path(source).stem
        ids = [f"{policy_name}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source, "chunk": i} for i in range(len(chunks))]
        
        # Add to collection
        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )
        
        return len(chunks)


# Example usage
if __name__ == "__main__":
    rag = RAGManager()
    
    print("RAG Manager Test")
    print("=" * 60)
    
    # Stats
    stats = rag.get_stats()
    print(f"\nDatabase Stats:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Policies: {stats['policies']}")
    
    # Search
    query = "travel allowance"
    results = rag.search(query, limit=2)
    print(f"\nSearch for '{query}':")
    for i, doc in enumerate(results, 1):
        print(f"  {i}. {doc[:100]}...")
    
    # Context
    context = rag.get_context("expense approval limits", limit=2)
    print(f"\nContext for 'expense approval limits':")
    print(f"  {context[:200]}...")
