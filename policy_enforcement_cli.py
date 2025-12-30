#!/usr/bin/env python3
"""
Policy Enforcement Engine - Interactive CLI Tool
Complete end-to-end workflow in a single script:
1. Extract policy from PDF
2. Generate rules & grades
3. Start API server
4. Accept user requests interactively
5. Evaluate and return decisions
"""

import os
import sys
import json
import subprocess
import time
import requests
from pathlib import Path
from datetime import datetime

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class PolicyEnforcementCLI:
    def __init__(self):
        self.api_url = "http://127.0.0.1:5000"
        self.api_server_process = None
        self.rules_loaded = False
        self.policies = {}
        self.cache_file = ".policy_cache.json"
        self.cache = self._load_cache()
        
    def _load_cache(self):
        """Load cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {'last_pdf': None, 'last_extracted': None}
    
    def _save_cache(self, pdf_path):
        """Save cache to file"""
        self.cache = {
            'last_pdf': pdf_path,
            'last_extracted': datetime.now().isoformat()
        }
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.print_warning(f"Could not save cache: {e}")
    
    def _is_same_pdf(self, pdf_path):
        """Check if PDF is the same as last processed"""
        # Get absolute path for comparison
        pdf_abs = os.path.abspath(pdf_path)
        last_pdf = self.cache.get('last_pdf')
        
        if last_pdf:
            last_abs = os.path.abspath(last_pdf)
            return pdf_abs == last_abs
        return False
    
    def print_header(self, text):
        """Print formatted header"""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}{text}{RESET}")
        print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")
    
    def print_success(self, text):
        """Print success message"""
        print(f"{GREEN}✓ {text}{RESET}")
    
    def print_error(self, text):
        """Print error message"""
        print(f"{RED}✗ {text}{RESET}")
    
    def print_info(self, text):
        """Print info message"""
        print(f"{BLUE}ℹ {text}{RESET}")
    
    def print_warning(self, text):
        """Print warning message"""
        print(f"{YELLOW}⚠ {text}{RESET}")
    
    def get_pdf_file(self):
        """Get PDF file from user"""
        self.print_header("STEP 1: SELECT POLICY PDF")
        
        while True:
            pdf_path = input(f"{BOLD}Enter PDF file path: {RESET}").strip()
            
            if not pdf_path:
                self.print_error("Path cannot be empty")
                continue
            
            # Handle quoted paths
            if pdf_path.startswith('"') and pdf_path.endswith('"'):
                pdf_path = pdf_path[1:-1]
            if pdf_path.startswith("'") and pdf_path.endswith("'"):
                pdf_path = pdf_path[1:-1]
            
            if not os.path.exists(pdf_path):
                self.print_error(f"File not found: {pdf_path}")
                continue
            
            if not pdf_path.lower().endswith(('.pdf', '.docx', '.txt')):
                self.print_error("Only PDF, DOCX, or TXT files are supported")
                continue
            
            self.print_success(f"Found: {pdf_path}")
            return pdf_path
    
    def cleanup_old_artifacts(self):
        """Clean up old artifacts before extraction"""
        self.print_info("Cleaning up old artifacts...")
        
        artifacts = ['chroma_db', 'rules.json', 'rules.db']
        for artifact in artifacts:
            try:
                if os.path.isdir(artifact):
                    import shutil
                    shutil.rmtree(artifact)
                    self.print_success(f"Removed directory: {artifact}")
                elif os.path.isfile(artifact):
                    os.remove(artifact)
                    self.print_success(f"Removed file: {artifact}")
            except Exception as e:
                self.print_warning(f"Could not remove {artifact}: {e}")
    
    def extract_policy(self, pdf_path):
        """Extract policy and generate rules"""
        self.print_header("STEP 2: EXTRACT POLICY & GENERATE RULES")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            # Default API key if not set in environment
            api_key = 'AIzaSyB_R1IyNoViLuHX313A9vUyXd1M-Vr5uR4'
            os.environ['GEMINI_API_KEY'] = api_key
        
        # Check if this is the same PDF as last time
        if self._is_same_pdf(pdf_path):
            # Validate that artifacts actually exist (cache can be stale)
            has_vector_db = os.path.exists('chroma_db') and os.path.exists('chroma_db/chroma.sqlite3')
            has_rules_db = os.path.exists('rules.db')
            
            if has_vector_db and has_rules_db:
                self.print_success("Using cached extraction (same PDF)")
                self.print_info("Artifacts already exist:")
                self.print_info("  ✓ chroma_db/ (vector database)")
                self.print_info("  ✓ rules.db (grade hierarchy)")
                self.print_info(f"Last extracted: {self.cache.get('last_extracted', 'Unknown')}")
                self.rules_loaded = True
                return True
            else:
                self.print_warning("Cache artifacts missing, re-extracting...")
        
        # Different PDF - clean up old artifacts and reset policies cache
        self.cleanup_old_artifacts()
        self.policies = {}  # Clear cached policies from previous PDF
        
        self.print_info(f"Extracting policy from: {pdf_path}")
        
        try:
            result = subprocess.run(
                ['python3', 'extract_policy.py', 'extract', pdf_path, '--rules'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                self.print_error("Policy extraction failed")
                print(result.stderr)
                return False
            
            # Parse output for key metrics
            output = result.stdout
            if '[SAVED]' in output:
                self.print_success("Policy extracted and rules generated")
            
            if '[GRADES]' in output:
                self.print_success("Grade hierarchies extracted")
            
            # Show extraction summary
            if '[TOTAL]' in output:
                for line in output.split('\n'):
                    if '[TOTAL]' in line or '[SAVED]' in line or '[GRADES]' in line or 'Level' in line:
                        print(f"  {line.strip()}")
            
            # Save to cache
            self._save_cache(pdf_path)
            self.print_success("Extraction cached for future use")
            
            self.rules_loaded = True
            return True
        
        except subprocess.TimeoutExpired:
            self.print_error("Extraction timed out")
            return False
        except Exception as e:
            self.print_error(f"Extraction failed: {e}")
            return False
    
    def start_api_server(self):
        """Start Flask API server"""
        self.print_header("STEP 3: START API SERVER")
        
        # Kill any existing API server on port 5000
        self.print_info("Cleaning up any existing API servers...")
        try:
            subprocess.run(
                "lsof -ti:5000 | xargs kill -9 2>/dev/null || true",
                shell=True,
                timeout=3
            )
            time.sleep(1)
        except:
            pass
        
        self.print_info("Starting API server on http://127.0.0.1:5000...")
        
        try:
            # Start server in background (write to temp file for debugging)
            self.api_server_process = subprocess.Popen(
                ['python3', 'api_server.py'],
                stdout=open('/tmp/api_server.log', 'w'),
                stderr=subprocess.STDOUT
            )
            
            # Wait for server to start (increased timeout for initialization)
            time.sleep(8)
            
            # Check if server is running
            try:
                response = requests.get(f"{self.api_url}/health", timeout=5)
                if response.status_code == 200:
                    self.print_success("API server started successfully")
                    return True
            except:
                pass
            
            self.print_error("API server failed to start")
            return False
        
        except Exception as e:
            self.print_error(f"Failed to start API server: {e}")
            return False
    
    def load_policies(self, force_reload=False):
        """Load available policies from API"""
        try:
            # Force reload by adding timestamp to bypass any caching
            url = f"{self.api_url}/api/policies"
            if force_reload:
                url += f"?_t={time.time()}"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.policies = data.get('policies', {})
                return True
        except:
            pass
        return False
    
    def display_policies(self):
        """Display available policies"""
        if not self.policies:
            self.print_warning("No policies loaded")
            return
        
        print(f"\n{BOLD}Available Policies:{RESET}")
        for i, (policy_name, policy_info) in enumerate(self.policies.items(), 1):
            rule_count = policy_info.get('rule_count', 0)
            print(f"  {i}. {policy_name} ({rule_count} rules)")
    
    def get_user_input_field(self, field_name, field_type="string", required=True):
        """Get user input for a field"""
        type_hint = {
            "string": "text",
            "integer": "number",
            "float": "decimal",
            "boolean": "yes/no"
        }.get(field_type, "value")
        
        while True:
            value = input(f"  {field_name} ({type_hint}): ").strip()
            
            if not value and required:
                self.print_warning(f"{field_name} is required")
                continue
            
            if not value:
                return None
            
            # Type conversion
            try:
                if field_type == "integer":
                    return int(value)
                elif field_type == "float":
                    return float(value)
                elif field_type == "boolean":
                    return value.lower() in ['yes', 'true', 'y', '1']
                else:
                    return value
            except ValueError:
                self.print_error(f"Invalid {field_type}: {value}")
                continue
    
    def build_request_payload(self):
        """Build request payload interactively or via JSON paste"""
        self.print_header("STEP 4: BUILD REQUEST PAYLOAD")
        
        print(f"{BOLD}How would you like to provide the payload?{RESET}")
        print("  1. Paste JSON (paste entire payload)")
        print("  2. Enter fields manually")
        
        choice = input(f"\n{BOLD}Select option (1-2): {RESET}").strip()
        
        if choice == "1":
            return self._build_payload_from_json()
        else:
            return self._build_payload_interactively()
    
    def _build_payload_from_json(self):
        """Build payload by pasting JSON"""
        print(f"\n{BOLD}Paste your JSON payload and press Enter twice when done:{RESET}\n")
        
        lines = []
        empty_count = 0
        
        while True:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 1:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        
        json_str = "\n".join(lines)
        
        try:
            payload = json.loads(json_str)
            
            # Ensure request_id exists
            if "request_id" not in payload:
                payload["request_id"] = f"REQ_{int(time.time())}"
            
            self.print_success("Payload parsed successfully")
            return payload
        except json.JSONDecodeError as e:
            self.print_error(f"Invalid JSON: {e}")
            self.print_info("Falling back to manual entry...")
            return self._build_payload_interactively()
    
    def _build_payload_interactively(self):
        """Build request payload interactively (original method)"""
        request_id = input(f"{BOLD}Request ID (e.g., REQ_001): {RESET}").strip()
        if not request_id:
            request_id = f"REQ_{int(time.time())}"
        
        payload = {"request_id": request_id}
        
        print(f"\n{BOLD}Enter request fields (press Enter to skip optional fields):{RESET}\n")
        
        # Get common fields
        common_fields = [
            ("grade", "string", True),
            ("destination_country", "string", False),
            ("purpose", "string", False),
            ("travel_duration_days", "integer", False),
            ("employee_status", "string", False),
            ("department", "string", False),
            ("expense_amount", "float", False),
        ]
        
        for field_name, field_type, required in common_fields:
            value = self.get_user_input_field(field_name, field_type, required)
            if value is not None:
                payload[field_name] = value
        
        print(f"\n{BOLD}Add custom fields? (yes/no): {RESET}", end="")
        if input().strip().lower() in ['yes', 'y']:
            while True:
                field_name = input("  Field name (or 'done'): ").strip()
                if field_name.lower() == 'done':
                    break
                if not field_name:
                    continue
                
                value = input("  Value: ").strip()
                if value:
                    # Try to convert to number if possible
                    try:
                        if '.' in value:
                            payload[field_name] = float(value)
                        else:
                            payload[field_name] = int(value)
                    except ValueError:
                        payload[field_name] = value
        
        return payload
    
    def send_request(self, payload):
        """Send request to API"""
        try:
            self.print_info(f"Sending request: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.api_url}/api/evaluate",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.print_error(f"API error: {response.status_code}")
                print(response.text)
                return None
        
        except Exception as e:
            self.print_error(f"Request failed: {e}")
            return None
    
    def display_result(self, result):
        """Display evaluation result"""
        self.print_header("EVALUATION RESULT")
        
        decision = result.get('decision', 'UNKNOWN')
        decision_color = GREEN if decision == 'APPROVE' else RED
        
        print(f"{BOLD}Decision:{RESET} {decision_color}{decision}{RESET}")
        print(f"{BOLD}Reason:{RESET} {result.get('primary_reason', 'N/A')}")
        
        # Show applicable rules
        applicable_rules = result.get('applicable_rules', [])
        if applicable_rules:
            print(f"\n{BOLD}Applicable Rules:{RESET}")
            for rule in applicable_rules:
                print(f"  • {rule}")
        
        # Show approvals
        approvals = result.get('approvals', [])
        if approvals:
            print(f"\n{BOLD}Approvals:{RESET}")
            for approval in approvals:
                rule_id = approval.get('rule_id')
                allocation = approval.get('allocation')
                period = approval.get('period')
                if allocation:
                    print(f"  {GREEN}✓{RESET} {rule_id}: {allocation} {period}")
                else:
                    print(f"  {GREEN}✓{RESET} {rule_id}")
        
        # Show violations
        violations = result.get('violations', [])
        if violations:
            print(f"\n{BOLD}Violations:{RESET}")
            for violation in violations:
                rule_id = violation.get('rule_id')
                message = violation.get('message')
                print(f"  {RED}✗{RESET} {rule_id}: {message}")
        
        # Save result to file
        result_file = f"result_{result.get('request_id', 'unknown')}.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        self.print_success(f"Result saved to: {result_file}")
    
    def run_interactive_loop(self):
        """Run interactive evaluation loop"""
        self.print_header("INTERACTIVE REQUEST EVALUATION")
        
        while True:
            print(f"\n{BOLD}Options:{RESET}")
            print("  1. Send new request")
            print("  2. Show available policies")
            print("  3. Exit")
            
            choice = input(f"\n{BOLD}Select option (1-3): {RESET}").strip()
            
            if choice == "1":
                payload = self.build_request_payload()
                print(f"\n{BOLD}Payload:{RESET}")
                print(json.dumps(payload, indent=2))
                
                confirm = input(f"\n{BOLD}Send this request? (yes/no): {RESET}").strip()
                if confirm.lower() in ['yes', 'y']:
                    result = self.send_request(payload)
                    if result:
                        self.display_result(result)
                    else:
                        self.print_error("Failed to get result")
            
            elif choice == "2":
                self.display_policies()
            
            elif choice == "3":
                break
            
            else:
                self.print_error("Invalid option")
    
    def cleanup(self):
        """Clean up resources"""
        if self.api_server_process:
            self.print_info("Stopping API server...")
            self.api_server_process.terminate()
            try:
                self.api_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.api_server_process.kill()
        
        # Also kill any remaining processes on port 5000
        try:
            subprocess.run(
                "lsof -ti:5000 | xargs kill -9 2>/dev/null || true",
                shell=True,
                timeout=3
            )
        except:
            pass
    
    def run(self):
        """Main workflow"""
        try:
            self.print_header("POLICY ENFORCEMENT ENGINE - CLI TOOL")
            print("Complete workflow: Extract → Evaluate → Decide\n")
            
            # Step 1: Get PDF
            pdf_path = self.get_pdf_file()
            
            # Step 2: Extract policy
            if not self.extract_policy(pdf_path):
                return
            
            # Step 3: Start API server
            if not self.start_api_server():
                return
            
            # Load policies (force reload to get fresh rules from new PDF)
            if not self.load_policies(force_reload=True):
                self.print_warning("Could not load policies from API")
            
            # Step 4: Interactive evaluation loop
            self.run_interactive_loop()
            
            self.print_success("Workflow completed")
        
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted by user{RESET}")
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
        finally:
            self.cleanup()


def main():
    """Entry point"""
    # Check requirements
    required_modules = ['requests', 'flask']
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print(f"{RED}Missing required modules: {', '.join(missing)}{RESET}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)
    
    # Set default API key if not already set
    if not os.getenv('GEMINI_API_KEY'):
        os.environ['GEMINI_API_KEY'] = 'AIzaSyB_R1IyNoViLuHX313A9vUyXd1M-Vr5uR4'
    
    # Run CLI
    cli = PolicyEnforcementCLI()
    cli.run()


if __name__ == "__main__":
    main()
