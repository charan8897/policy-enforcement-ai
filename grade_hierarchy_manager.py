#!/usr/bin/env python3
"""
Dynamic Grade Hierarchy Manager
Extracts grade hierarchies from policies using Gemini API
and stores them for use during rule evaluation.

This makes grade comparisons work across different policies and organizations.
"""

import os
import json
import sqlite3
from datetime import datetime
import google.generativeai as genai

try:
    import chromadb
except ImportError:
    chromadb = None


class GradeHierarchyDatabase:
    """SQLite database for storing grade hierarchies per policy"""
    
    def __init__(self, db_path="rules.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Create table for grade hierarchies"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS grade_hierarchies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                grade_name TEXT NOT NULL,
                grade_level INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(policy_id, grade_name)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS grade_hierarchy_metadata (
                policy_id TEXT PRIMARY KEY,
                policy_name TEXT NOT NULL,
                source_type TEXT,
                extraction_method TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_custom INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def insert_grade(self, policy_id, policy_name, grade_name, grade_level, description=None):
        """Insert a grade into the hierarchy"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO grade_hierarchies 
                (policy_id, policy_name, grade_name, grade_level, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (policy_id, policy_name, grade_name, grade_level, description))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to insert grade: {e}")
            return False
    
    def insert_hierarchy_metadata(self, policy_id, policy_name, source_type, extraction_method):
        """Insert hierarchy metadata"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO grade_hierarchy_metadata
                (policy_id, policy_name, source_type, extraction_method)
                VALUES (?, ?, ?, ?)
            ''', (policy_id, policy_name, source_type, extraction_method))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to insert metadata: {e}")
            return False
    
    def get_hierarchy_for_policy(self, policy_id):
        """Get grade hierarchy for a specific policy"""
        self.cursor.execute('''
            SELECT grade_name, grade_level 
            FROM grade_hierarchies 
            WHERE policy_id = ? 
            ORDER BY grade_level ASC
        ''', (policy_id,))
        
        hierarchy = {}
        for row in self.cursor.fetchall():
            hierarchy[row['grade_name']] = row['grade_level']
        
        return hierarchy if hierarchy else None
    
    def get_all_hierarchies(self):
        """Get all grade hierarchies"""
        self.cursor.execute('''
            SELECT DISTINCT policy_id, policy_name 
            FROM grade_hierarchies
        ''')
        
        result = {}
        for row in self.cursor.fetchall():
            policy_id = row['policy_id']
            hierarchy = self.get_hierarchy_for_policy(policy_id)
            if hierarchy:
                result[policy_id] = {
                    'policy_name': row['policy_name'],
                    'hierarchy': hierarchy
                }
        
        return result
    
    def export_to_json(self, output_file):
        """Export all grade hierarchies to JSON"""
        hierarchies = self.get_all_hierarchies()
        
        with open(output_file, 'w') as f:
            json.dump(hierarchies, f, indent=2)
        
        print(f"[EXPORT] Saved grade hierarchies to {output_file}")
        return len(hierarchies)
    
    def close(self):
        """Close database connection"""
        self.conn.close()


class GradeHierarchyExtractor:
    """Extract grade hierarchies from policies using Gemini API"""
    
    def __init__(self, api_key, db_path="rules.db", chroma_path="./chroma_db"):
        """Initialize with Gemini API and database"""
        self.api_key = api_key
        self.chroma_path = chroma_path
        self.db = GradeHierarchyDatabase(db_path)
        
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
            raise Exception("Chroma not installed. Install with: pip install chromadb")
        
        self.client = chromadb.PersistentClient(path=chroma_path)
        try:
            self.collection = self.client.get_collection(name="policies")
        except Exception as e:
            raise Exception(f"Vector DB not found: {e}")
    
    def extract_for_policy(self, policy_id, policy_name):
        """Extract grade hierarchy for a specific policy"""
        print(f"\n[EXTRACTING] Grade hierarchy for: {policy_name}")
        
        # Get policy text from RAG
        try:
            results = self.collection.query(
                query_texts=[policy_name],
                n_results=10
            )
            policy_text = "\n".join(results['documents'][0][:10]) if results['documents'] else ""
        except Exception as e:
            print(f"[ERROR] Could not retrieve policy from RAG: {e}")
            return False
        
        if not policy_text:
            print("[WARNING] No policy text found")
            return False
        
        # Extract grades using LLM
        grades = self._extract_grades_from_text(policy_text, policy_name)
        
        if not grades:
            print("[WARNING] No grades extracted")
            return False
        
        # Build hierarchy (assign levels)
        hierarchy = self._build_hierarchy(grades)
        
        # Store in database
        self.db.insert_hierarchy_metadata(
            policy_id,
            policy_name,
            source_type='RAG_VECTOR_DB',
            extraction_method='GEMINI_LLM'
        )
        
        for grade, level in hierarchy.items():
            self.db.insert_grade(policy_id, policy_name, grade, level)
        
        print(f"[SAVED] {len(hierarchy)} grades extracted and saved")
        for grade, level in sorted(hierarchy.items(), key=lambda x: x[1]):
            print(f"  Level {level}: {grade}")
        
        return True
    
    def _extract_grades_from_text(self, policy_text, policy_name):
        """Extract grade definitions from policy text using LLM"""
        prompt = f"""
Extract all INDIVIDUAL employee grades/levels mentioned in this policy document.
Do NOT extract ranges like "E8 to E10" - extract individual grades.

Policy: {policy_name}

Text:
{policy_text[:3000]}

Return ONLY a JSON array of individual grade names.
Example: ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "Directors", "CEO"]

Important:
- Extract INDIVIDUAL grades only (not ranges)
- Break down ranges: "E8 to E10" → ["E8", "E9", "E10"]
- Extract exact grade names as they appear in the policy
- Include all designations/levels mentioned
- Return only valid JSON array

JSON array:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                return []
            
            json_str = response_text[start:end]
            grades = json.loads(json_str)
            
            return [g.strip() for g in grades if g.strip()]
        
        except Exception as e:
            print(f"[ERROR] Grade extraction failed: {e}")
            return []
    
    def _build_hierarchy(self, grades):
        """Build hierarchy by assigning levels to grades"""
        # Ask LLM to determine the hierarchy order
        prompt = f"""
Determine the seniority hierarchy for these grades (highest seniority first).

Grades: {json.dumps(grades)}

Return a JSON object mapping grade name to numeric level.
Highest seniority should have the highest number.

Example:
{{
  "E1": 1,
  "E2": 2,
  "E3": 3,
  "Senior Manager": 10,
  "Director": 11,
  "CEO": 12
}}

Important:
- Return only valid JSON object
- Use reasonable numeric levels
- Higher number = higher seniority

JSON object:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start < 0 or end <= start:
                # Fallback: assign sequential levels
                return {grade: i+1 for i, grade in enumerate(sorted(grades))}
            
            json_str = response_text[start:end]
            hierarchy = json.loads(json_str)
            
            # Convert values to integers
            return {k: int(v) for k, v in hierarchy.items()}
        
        except Exception as e:
            print(f"[ERROR] Hierarchy building failed: {e}")
            # Fallback: assign sequential levels
            return {grade: i+1 for i, grade in enumerate(sorted(grades))}
    
    def close(self):
        """Close database connection"""
        self.db.close()


class DynamicGradeEvaluator:
    """Evaluate grades dynamically using extracted hierarchies"""
    
    def __init__(self, db_path="rules.db"):
        """Initialize with database"""
        self.db = GradeHierarchyDatabase(db_path)
        self.hierarchies = self.db.get_all_hierarchies()
    
    def get_grade_level(self, grade_name, policy_id=None):
        """Get numeric level for a grade"""
        # If policy_id specified, use that hierarchy
        if policy_id:
            hierarchy = self.db.get_hierarchy_for_policy(policy_id)
            if hierarchy and grade_name in hierarchy:
                return hierarchy[grade_name]
        
        # Search across all hierarchies
        for pid, data in self.hierarchies.items():
            if grade_name in data['hierarchy']:
                return data['hierarchy'][grade_name]
        
        # Fallback: try numeric conversion
        try:
            return float(grade_name)
        except (ValueError, TypeError):
            return None
    
    def compare_grades(self, grade1, grade2, policy_id=None):
        """Compare two grades. Returns: -1 (grade1 < grade2), 0 (equal), 1 (grade1 > grade2)"""
        level1 = self.get_grade_level(grade1, policy_id)
        level2 = self.get_grade_level(grade2, policy_id)
        
        if level1 is None or level2 is None:
            return None  # Cannot compare
        
        if level1 < level2:
            return -1
        elif level1 > level2:
            return 1
        else:
            return 0
    
    def close(self):
        """Close database connection"""
        self.db.close()


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python grade_hierarchy_manager.py <command> [options]")
        print("\nCommands:")
        print("  extract <policy_id> <policy_name>  # Extract hierarchy for policy")
        print("  list                               # List all extracted hierarchies")
        print("  compare <grade1> <grade2>          # Compare two grades")
        print("  export-json <file>                 # Export all hierarchies to JSON")
        print("\nExamples:")
        print("  python grade_hierarchy_manager.py extract POL_OVE 'Overseas Business Travel'")
        print("  python grade_hierarchy_manager.py list")
        print("  python grade_hierarchy_manager.py export-json grades.json")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'extract':
        if len(sys.argv) < 4:
            print("[ERROR] Missing policy_id or policy_name")
            sys.exit(1)
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[ERROR] GEMINI_API_KEY not set")
            sys.exit(1)
        
        policy_id = sys.argv[2]
        policy_name = sys.argv[3]
        
        try:
            extractor = GradeHierarchyExtractor(api_key)
            success = extractor.extract_for_policy(policy_id, policy_name)
            extractor.close()
            sys.exit(0 if success else 1)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'list':
        try:
            db = GradeHierarchyDatabase()
            hierarchies = db.get_all_hierarchies()
            
            if not hierarchies:
                print("[INFO] No hierarchies found")
            else:
                print(f"\n{'='*60}")
                print(f"Grade Hierarchies ({len(hierarchies)})")
                print(f"{'='*60}")
                
                for policy_id, data in hierarchies.items():
                    print(f"\n{data['policy_name']} ({policy_id}):")
                    for grade, level in sorted(data['hierarchy'].items(), key=lambda x: x[1]):
                        print(f"  Level {level}: {grade}")
            
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'compare':
        if len(sys.argv) < 4:
            print("[ERROR] Missing grade1 or grade2")
            sys.exit(1)
        
        grade1 = sys.argv[2]
        grade2 = sys.argv[3]
        
        try:
            evaluator = DynamicGradeEvaluator()
            result = evaluator.compare_grades(grade1, grade2)
            
            if result is None:
                print(f"[ERROR] Cannot compare {grade1} and {grade2}")
            else:
                if result < 0:
                    print(f"{grade1} < {grade2}")
                elif result > 0:
                    print(f"{grade1} > {grade2}")
                else:
                    print(f"{grade1} == {grade2}")
            
            evaluator.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    elif command == 'export-json':
        if len(sys.argv) < 3:
            print("[ERROR] Missing output file")
            sys.exit(1)
        
        output_file = sys.argv[2]
        
        try:
            db = GradeHierarchyDatabase()
            db.export_to_json(output_file)
            db.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    
    else:
        print(f"[ERROR] Unknown command: {command}")
        sys.exit(1)
