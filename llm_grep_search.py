#!/usr/bin/env python3
"""
LLM-Based Grep Search for Policy Rules
Uses Gemini 2.5 Flash to intelligently search through policy rules
With fallback retries and response logging
"""

import os
import sys
import subprocess
import json
import google.generativeai as genai
from datetime import datetime
from pathlib import Path

class LLMGrepSearch:
    def __init__(self, api_key, rules_file="rules.json", log_file="grep_search_log.json"):
        """Initialize with Gemini API key"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemma-3-27b-it')
        self.rules_file = rules_file
        self.log_file = log_file
        self.max_retries = 3
        self.attempt_log = []
    
    def search(self, user_query):
        """Main search method - LLM generates grep commands"""
        print(f"\n{'='*70}")
        print(f"LLM-Based Policy Search")
        print(f"{'='*70}")
        print(f"[QUERY] {user_query}")
        
        for attempt in range(1, self.max_retries + 1):
            print(f"\n[ATTEMPT {attempt}/{self.max_retries}]")
            
            # Get context from previous attempts
            context = self._build_context(user_query, attempt)
            
            # Ask LLM to generate grep command
            grep_command = self._llm_generate_command(user_query, context)
            
            if not grep_command:
                print(f"[ERROR] LLM failed to generate command")
                continue
            
            print(f"[COMMAND] {grep_command}")
            
            # Execute the command
            result = self._execute_command(grep_command)
            
            # Log the attempt
            self._log_attempt(attempt, user_query, grep_command, result)
            
            # Check if successful
            if result['success']:
                print(f"[SUCCESS] Found {result['match_count']} results")
                self._display_results(result['output'])
                return result
            else:
                print(f"[FAILED] {result['error']}")
                if attempt < self.max_retries:
                    print(f"[RETRY] Attempting different approach...")
        
        print(f"\n[FINAL] Could not find results after {self.max_retries} attempts")
        return {'success': False, 'message': 'Search failed'}
    
    def _llm_generate_command(self, user_query, context):
        """Ask LLM to generate grep command"""
        
        context_info = ""
        if context and context.get('previous_attempts'):
            context_info = f"""
Previous attempts failed:
{json.dumps(context['previous_attempts'], indent=2)}

Instruction: {context.get('instruction')}
Try searching for related keywords or use partial matching instead."""
        
        prompt = f"""
You are a grep command expert. Generate a grep command to search policy rules JSON file.

User Query: {user_query}

Rules file: {self.rules_file}

{context_info}

Generate ONLY a valid grep command. Examples:
- grep -i "annual leave" {self.rules_file}
- grep -E "sick|doctor" {self.rules_file}
- grep "RULE_" {self.rules_file}

Requirements:
- Search {self.rules_file}
- Use grep flags: -i (case-insensitive), -E (regex for OR patterns)
- Return ONLY the command, no code blocks, no explanation

Command:"""
        
        try:
            response = self.model.generate_content(prompt)
            command = response.text.strip()
            
            # Clean up if wrapped in code blocks
            if command.startswith('```'):
                command = command.split('\n')[1]
            if command.endswith('```'):
                command = command.rsplit('\n', 1)[0]
            
            return command
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return None
    
    def _execute_command(self, grep_command):
        """Execute grep command safely"""
        try:
            result = subprocess.run(
                grep_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                cwd="/home/hutech/Downloads/policy enforcement engine"
            )
            
            output = result.stdout.strip()
            
            if result.returncode == 0 and output:
                match_count = len(output.split('\n'))
                return {
                    'success': True,
                    'output': output,
                    'match_count': match_count,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'output': output,
                    'match_count': 0,
                    'error': result.stderr or "No matches found"
                }
        except subprocess.TimeoutExpired:
            return {'success': False, 'output': '', 'match_count': 0, 'error': 'Command timeout'}
        except Exception as e:
            return {'success': False, 'output': '', 'match_count': 0, 'error': str(e)}
    
    def _build_context(self, user_query, current_attempt):
        """Build context from previous attempts for LLM"""
        if current_attempt == 1:
            return {}
        
        # Get last attempt
        recent_attempts = [
            {
                'command': log['command'],
                'error': log['result'].get('error'),
                'match_count': log['result'].get('match_count', 0),
                'output_preview': log['result'].get('output_preview')
            }
            for log in self.attempt_log[-2:]  # Last 2 attempts
        ]
        
        return {
            'previous_attempts': recent_attempts,
            'instruction': 'Try a different grep pattern or flag if previous attempt failed'
        }
    
    def _log_attempt(self, attempt, query, command, result):
        """Log each search attempt"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'attempt': attempt,
            'query': query,
            'command': command,
            'result': {
                'success': result['success'],
                'match_count': result['match_count'],
                'error': result['error'],
                'output_preview': result['output'][:200] if result['output'] else None
            }
        }
        self.attempt_log.append(log_entry)
    
    def _display_results(self, output, max_lines=10):
        """Display search results"""
        lines = output.split('\n')
        display_lines = lines[:max_lines]
        
        print(f"\n[RESULTS]")
        for line in display_lines:
            print(f"  {line}")
        
        if len(lines) > max_lines:
            print(f"  ... and {len(lines) - max_lines} more")
    
    def save_log(self):
        """Save search attempt log"""
        with open(self.log_file, 'w') as f:
            json.dump(self.attempt_log, f, indent=2)
        print(f"\n[LOG] Saved to {self.log_file}")
    
    def interactive_search(self):
        """Run interactive search loop"""
        print("\nInteractive Policy Search (type 'quit' to exit)")
        print("-" * 70)
        
        while True:
            query = input("\n[SEARCH] Enter query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            result = self.search(query)
            self.save_log()


def main():
    """Main entry point"""
    api_key = "AIzaSyBNA3ulr_NxSCa8S3emQk_GH-jIwwydCdc"
    
    if len(sys.argv) > 1:
        # Single query mode
        query = ' '.join(sys.argv[1:])
        searcher = LLMGrepSearch(api_key)
        result = searcher.search(query)
        searcher.save_log()
    else:
        # Interactive mode
        searcher = LLMGrepSearch(api_key)
        searcher.interactive_search()


if __name__ == "__main__":
    main()
