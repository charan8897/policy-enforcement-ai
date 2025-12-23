#!/usr/bin/env python3
"""
Simple Web Scraper for Policy Documents
Lightweight scraper without LLM dependencies
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

class SimplePolicyScraper:
    def __init__(self, timeout=10):
        """Initialize scraper"""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, url, output_file="policy.txt"):
        """Scrape URL and save content"""
        print(f"\n{'='*60}")
        print(f"Web Policy Scraper")
        print(f"{'='*60}")
        print(f"[URL] {url}")
        
        try:
            print(f"[STEP 1] Fetching page...")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            print(f"[STEP 2] Parsing HTML...")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script, style, nav, footer, header
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(clean_text)
            
            print(f"[STEP 3] Saving content...")
            print(f"\n[OUTPUT] Saved to: {output_file}")
            print(f"[OUTPUT] Size: {len(clean_text)} characters, {len(lines)} lines")
            print(f"{'='*60}\n")
            
            return True
        
        except Exception as e:
            print(f"\n[ERROR] {e}\n")
            return False


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python web_scraper_simple.py <url> [output_file]")
        print("\nExamples:")
        print("  python web_scraper_simple.py https://handbook.gitlab.com/handbook/finance/expenses/")
        print("  python web_scraper_simple.py https://example.com/policy policy.txt")
        sys.exit(1)
    
    url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "policy.txt"
    
    scraper = SimplePolicyScraper()
    success = scraper.scrape(url, output_file)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
