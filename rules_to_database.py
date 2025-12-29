#!/usr/bin/env python3
"""
Rules Generation and Database Storage
Automatically generates separate rules from policies using Gemini API
and saves them to a database table with full RAG traceability.

Workflow:
1. Extract policy to RAG (creates ./chroma_db/)
2. Initialize RuleExtractor (connects to Gemini API + Chroma DB)
3. Detect policy types dynamically from RAG
4. For each policy type:
   - Query RAG semantically for relevant chunks
   - Send to Gemini for rule extraction
   - Gemini returns JSON array of rules
5. Collect, deduplicate, and add metadata
6. Save to database table with RAG traceability

Usage:
    export GEMINI_API_KEY=[your-key]
    python3 rules_to_database.py --policy overseas_travel.pdf --db rules.db
    python3 rules_to_database.py --list-policies
    python3 rules_to_database.py --export-json rules.json
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

try:
    import chromadb
except ImportError:
    chromadb = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None


class RulesDatabase:
    """SQLite database for storing extracted rules with RAG metadata"""
    
    def __init__(self, db_path="rules.db"):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        print(f"[DB] Connected to: {db_path}")
    
    def _create_tables(self):
        """Create necessary tables for rules storage"""
        # Main rules table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                conditions TEXT NOT NULL,
                action TEXT NOT NULL,
                allocation INTEGER,
                period TEXT,
                message TEXT,
                severity TEXT DEFAULT 'MEDIUM',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # RAG metadata table for traceability
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS rule_rag_metadata (
                rule_id TEXT PRIMARY KEY,
                db_path TEXT,
                collection_name TEXT,
                source_type TEXT,
                source_query TEXT,
                source_note TEXT,
                FOREIGN KEY(rule_id) REFERENCES rules(rule_id)
            )
        ''')
        
        # Rule source chunks table (stores which RAG chunks generated the rule)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS rule_source_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT,
                chunk_id TEXT,
                chunk_text TEXT,
                FOREIGN KEY(rule_id) REFERENCES rules(rule_id)
            )
        ''')
        
        # Policy table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                policy_id TEXT PRIMARY KEY,
                policy_name TEXT NOT NULL UNIQUE,
                source_file TEXT,
                total_rules INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def insert_rule(self, rule, rag_metadata=None, source_chunks=None):
        """Insert a rule into the database"""
        try:
            # Insert main rule
            self.cursor.execute('''
                INSERT OR REPLACE INTO rules 
                (rule_id, policy_id, policy_name, conditions, action, allocation, period, message, severity, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.get('rule_id'),
                rule.get('policy_id'),
                rule.get('policy_name'),
                json.dumps(rule.get('conditions', [])),
                rule.get('action'),
                rule.get('allocation'),
                rule.get('period'),
                rule.get('message'),
                rule.get('severity', 'MEDIUM'),
                datetime.now().isoformat()
            ))
            
            # Insert RAG metadata if provided
            if rag_metadata:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO rule_rag_metadata
                    (rule_id, db_path, collection_name, source_type, source_query, source_note)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    rule.get('rule_id'),
                    rag_metadata.get('db_path'),
                    rag_metadata.get('collection_name'),
                    rag_metadata.get('source_type'),
                    rag_metadata.get('source_query'),
                    rag_metadata.get('source_note')
                ))
            
            # Insert source chunks if provided
            if source_chunks:
                for chunk_id, chunk_text in source_chunks:
                    self.cursor.execute('''
                        INSERT INTO rule_source_chunks (rule_id, chunk_id, chunk_text)
                        VALUES (?, ?, ?)
                    ''', (rule.get('rule_id'), chunk_id, chunk_text))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to insert rule {rule.get('rule_id')}: {e}")
            return False
    
    def insert_policy(self, policy_id, policy_name, source_file=None, total_rules=0):
        """Insert policy metadata"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO policies (policy_id, policy_name, source_file, total_rules)
                VALUES (?, ?, ?, ?)
            ''', (policy_id, policy_name, source_file, total_rules))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to insert policy: {e}")
            return False
    
    def get_all_rules(self):
        """Retrieve all rules as dictionaries"""
        self.cursor.execute('SELECT * FROM rules')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_rules_by_policy(self, policy_name):
        """Get all rules for a specific policy"""
        self.cursor.execute('SELECT * FROM rules WHERE policy_name = ?', (policy_name,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_rule_with_metadata(self, rule_id):
        """Get rule with its RAG metadata"""
        self.cursor.execute('SELECT * FROM rules WHERE rule_id = ?', (rule_id,))
        rule = self.cursor.fetchone()
        
        self.cursor.execute('SELECT * FROM rule_rag_metadata WHERE rule_id = ?', (rule_id,))
        metadata = self.cursor.fetchone()
        
        if rule:
            result = dict(rule)
            if metadata:
                result['_rag_metadata'] = dict(metadata)
            return result
        return None
    
    def get_stats(self):
        """Get database statistics"""
        self.cursor.execute('SELECT COUNT(*) as count FROM rules')
        total_rules = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM policies')
        total_policies = self.cursor.fetchone()['count']
        
        return {
            'total_rules': total_rules,
            'total_policies': total_policies,
            'db_path': self.db_path
        }
    
    def export_to_json(self, output_file):
        """Export all rules to JSON with metadata"""
        rules = self.get_all_rules()
        
        # Add RAG metadata to each rule
        for rule in rules:
            rule_id = rule['rule_id']
            self.cursor.execute('SELECT * FROM rule_rag_metadata WHERE rule_id = ?', (rule_id,))
            metadata = self.cursor.fetchone()
            if metadata:
                rule['_rag_metadata'] = dict(metadata)
            
            # Parse JSON fields
            rule['conditions'] = json.loads(rule.get('conditions', '[]'))
        
        with open(output_file, 'w') as f:
            json.dump(rules, f, indent=2)
        
        print(f"[EXPORT] Saved {len(rules)} rules to {output_file}")
        return len(rules)
    
    def close(self):
        """Close database connection"""
        self.conn.close()


class RuleExtractorWithDB:
    """Extract rules from policies and save to database"""
    
    def __init__(self, api_key, db_path="rules.db", chroma_path="./chroma_db"):
        """Initialize with Gemini API and database"""
        self.api_key = api_key
        self.chroma_path = chroma_path
        self.db = RulesDatabase(db_path)
        
        # Initialize Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            'gemma-3-27b-it',
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                top_p=0.95
            )
        )
        
        # Initialize Chroma
        if not chromadb:
            raise Exception("Chroma not installed. Install with: pip install chromadb langchain")
        
        self.client = chromadb.PersistentClient(path=chroma_path)
        try:
            self.collection = self.client.get_collection(name="policies")
            print(f"[RAG] Connected to vector DB: {chroma_path}/policies")
        except Exception as e:
            raise Exception(f"Vector DB not found. Run extraction first: {e}")
    
    def extract_and_save(self):
        """Main workflow: detect policies → extract rules → save to DB"""
        print(f"\n{'='*60}")
        print(f"Rule Extraction & Database Save")
        print(f"{'='*60}")
        
        # Step 1: Detect policy types
        policy_types = self._detect_policy_types()
        
        if not policy_types:
            print("[WARNING] No policy types detected")
            return False
        
        print(f"[DETECTED] {len(policy_types)} policy types:")
        for ptype in policy_types:
            print(f"  - {ptype}")
        
        # Step 2: Extract rules for each policy type
        all_rules = []
        rule_counter = 1
        
        for policy_type in policy_types:
            print(f"\n[EXTRACTING] {policy_type}...")
            rules = self._extract_rules_for_type(policy_type, rule_counter)
            
            if rules:
                all_rules.extend(rules)
                rule_counter += len(rules)
                print(f"  ✓ {len(rules)} rules found")
            else:
                print(f"  - No rules extracted")
        
        # Step 3: Save to database
        if all_rules:
            self._save_to_database(all_rules)
            print(f"\n[SUCCESS] {len(all_rules)} rules extracted and saved to database")
            return True
        else:
            print("[WARNING] No rules to save")
            return False
    
    def _detect_policy_types(self):
        """Detect policy types from RAG"""
        print("[DETECTING] Policy types from vector DB...")
        
        try:
            results = self.collection.get(limit=20)
            all_text = "\n".join(results['documents'][:10])
        except Exception as e:
            print(f"[ERROR] Could not query vector DB: {e}")
            return []
        
        prompt = f"""
Analyze this policy document and list all main policy types/categories.

Document excerpt:
{all_text[:3000]}

Return ONLY a JSON array of policy names (strings).
Example: ["Leave Policy", "Travel Policy"]

JSON array:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                return []
            
            json_str = response_text[start:end]
            policy_types = json.loads(json_str)
            return [p.strip() for p in policy_types if p.strip()]
        
        except Exception as e:
            print(f"[ERROR] Policy detection failed: {e}")
            return []
    
    def _extract_rules_for_type(self, policy_type, rule_start_id):
        """Extract rules for specific policy type"""
        
        # Get relevant chunks from RAG
        try:
            results = self.collection.query(
                query_texts=[policy_type],
                n_results=5
            )
            section = "\n".join(results['documents'][0][:5]) if results['documents'] else ""
            source_chunks = [(results['ids'][0][i], results['documents'][0][i]) 
                           for i in range(min(len(results['ids'][0]), len(results['documents'][0])))]
        except Exception as e:
            print(f"[ERROR] RAG query failed: {e}")
            return []
        
        prompt = f"""
Extract all policy rules for "{policy_type}". Return ONLY valid JSON array.

Policy section:
{section[:2000]}

Example format:
[
  {{
    "rule_id": "RULE_001",
    "policy_id": "POL_{policy_type.upper().replace(' ', '_')}",
    "policy_name": "{policy_type}",
    "conditions": [{{"field": "field_name", "operator": "equals", "value": "value"}}],
    "action": "ELIGIBLE",
    "allocation": 8,
    "period": "per_annum",
    "message": "description",
    "severity": "MEDIUM"
  }}
]

Requirements:
- Return ONLY JSON array
- Valid operators: equals, greater_than, less_than, greater_than_or_equals, in
- Each rule needs: rule_id, policy_id, policy_name, conditions, action, message

JSON:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                return []
            
            json_str = response_text[start:end]
            rules = json.loads(json_str)
            
            # Update rule IDs and add RAG metadata
            for i, rule in enumerate(rules):
                policy_prefix = policy_type.split()[0][:3].upper()
                rule['rule_id'] = f"RULE_{policy_prefix}_{rule_start_id + i:03d}"
                rule['_source'] = {
                    'type': 'RAG_VECTOR_DB',
                    'db_path': self.chroma_path,
                    'query': policy_type,
                    'note': 'Can retrieve source chunks using semantic search'
                }
                rule['_source_chunks'] = source_chunks
            
            return rules
        
        except Exception as e:
            print(f"[ERROR] Rule extraction failed: {e}")
            return []
    
    def _save_to_database(self, rules):
        """Save extracted rules to database with RAG metadata"""
        print(f"\n[SAVING] {len(rules)} rules to database...")
        
        saved_count = 0
        
        for rule in rules:
            # Prepare RAG metadata
            rag_metadata = {
                'db_path': self.chroma_path,
                'collection_name': 'policies',
                'source_type': rule.get('_source', {}).get('type'),
                'source_query': rule.get('_source', {}).get('query'),
                'source_note': rule.get('_source', {}).get('note')
            }
            
            # Prepare source chunks
            source_chunks = rule.get('_source_chunks', [])
            
            # Insert into database
            if self.db.insert_rule(rule, rag_metadata, source_chunks):
                saved_count += 1
            
            # Also insert/update policy
            self.db.insert_policy(
                rule.get('policy_id'),
                rule.get('policy_name'),
                source_file=self.chroma_path
            )
        
        print(f"[SUCCESS] Saved {saved_count}/{len(rules)} rules to database")
        
        # Display stats
        stats = self.db.get_stats()
        print(f"\n[STATS]")
        print(f"  Total rules: {stats['total_rules']}")
        print(f"  Total policies: {stats['total_policies']}")
        print(f"  Database: {stats['db_path']}")
    
    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python rules_to_database.py <command> [options]")
        print("\nCommands:")
        print("  extract              # Extract rules from RAG and save to database")
        print("  list-policies        # List all policies in database")
        print("  list-rules           # List all rules in database")
        print("  stats                # Show database statistics")
        print("  export-json <file>   # Export all rules to JSON file")
        print("\nOptions:")
        print("  --db <file>          # Database file (default: rules.db)")
        print("  --chroma <path>      # Chroma DB path (default: ./chroma_db)")
        print("\nExamples:")
        print("  python rules_to_database.py extract")
        print("  python rules_to_database.py extract --db mydb.db")
        print("  python rules_to_database.py list-rules")
        print("  python rules_to_database.py export-json rules.json")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Parse options
    db_path = "rules.db"
    chroma_path = "./chroma_db"
    
    if "--db" in sys.argv:
        idx = sys.argv.index("--db")
        if idx + 1 < len(sys.argv):
            db_path = sys.argv[idx + 1]
    
    if "--chroma" in sys.argv:
        idx = sys.argv.index("--chroma")
        if idx + 1 < len(sys.argv):
            chroma_path = sys.argv[idx + 1]
    
    if command == 'extract':
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[ERROR] GEMINI_API_KEY not set. Run: export GEMINI_API_KEY=your-key")
            sys.exit(1)
        
        try:
            extractor = RuleExtractorWithDB(api_key, db_path, chroma_path)
            success = extractor.extract_and_save()
            extractor.close()
            sys.exit(0 if success else 1)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'list-policies':
        try:
            db = RulesDatabase(db_path)
            db.cursor.execute('SELECT * FROM policies')
            policies = db.cursor.fetchall()
            
            if not policies:
                print("[INFO] No policies found")
            else:
                print(f"\n{'='*60}")
                print(f"Policies ({len(policies)})")
                print(f"{'='*60}")
                for policy in policies:
                    print(f"  {policy['policy_name']}: {policy['total_rules']} rules")
            
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'list-rules':
        try:
            db = RulesDatabase(db_path)
            rules = db.get_all_rules()
            
            if not rules:
                print("[INFO] No rules found")
            else:
                print(f"\n{'='*60}")
                print(f"Rules ({len(rules)})")
                print(f"{'='*60}")
                for rule in rules:
                    print(f"  {rule['rule_id']}: {rule['message']}")
            
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'stats':
        try:
            db = RulesDatabase(db_path)
            stats = db.get_stats()
            
            print(f"\n{'='*60}")
            print(f"Database Statistics")
            print(f"{'='*60}")
            print(f"  Database: {stats['db_path']}")
            print(f"  Total Rules: {stats['total_rules']}")
            print(f"  Total Policies: {stats['total_policies']}")
            
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'export-json':
        if len(sys.argv) < 3:
            print("[ERROR] Missing output file")
            sys.exit(1)
        
        output_file = sys.argv[2]
        
        try:
            db = RulesDatabase(db_path)
            db.export_to_json(output_file)
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    else:
        print(f"[ERROR] Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
