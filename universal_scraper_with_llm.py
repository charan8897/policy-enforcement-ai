#!/usr/bin/env python3
"""
Universal Web Scraper with LLM Verification
Works with ANY content type (policies, documents, articles, guides, etc.)
1. Scrape initial data (~1500 chars)
2. Feed to LLM for content verification
3. If unreliable, trigger DuckDuckGo search
4. LLM ranks search results by relevance
5. Scrape and verify each URL
6. Save all with confidence scores
"""

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import json
import time
import google.generativeai as genai
from urllib.parse import urlparse
import os

class UniversalScraperWithLLM:
#     def __init__(self, api_key, timeout=10, chunk_size=1500):
#         """Initialize with LLM and scraper"""
#         genai.configure(api_key=api_key)
#         self.model = genai.GenerativeModel('gemma-3-27b-it')
#         self.timeout = timeout
#         self.chunk_size = chunk_size
#         self.session = requests.Session()
#         self.session.headers.update({
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#         })
    
#     def scrape_content(self, url):
#         """Scrape main content from URL (removes navigation)"""
#         print(f"    [SCRAPE] {url}")
#         try:
#             response = self.session.get(url, timeout=self.timeout)
#             response.raise_for_status()
#             soup = BeautifulSoup(response.content, 'html.parser')
            
#             # Remove script, style, nav, footer tags
#             for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
#                 tag.decompose()
            
#             # Try to get main content area
#             main_content = soup.find('main')
#             if not main_content:
#                 main_content = soup.find('article')
#             if not main_content:
#                 main_content = soup.find('div', class_=['content', 'page-content', 'post', 'article'])
#             if not main_content:
#                 main_content = soup
            
#             # Extract text
#             text = main_content.get_text(separator='\n', strip=True)
            
#             # Clean up
#             lines = []
#             for line in text.split('\n'):
#                 line = line.strip()
#                 # Skip common nav items
#                 if line and len(line) > 3 and not any(x in line.lower() for x in ['skip to', 'menu', 'home', 'contact us', 'admissions']):
#                     lines.append(line)
            
#             text = '\n'.join(lines)
#             return text
#         except Exception as e:
#             print(f"    [ERROR] {e}")
#             return None
    
#     def verify_content_reliability(self, content, content_description, quality_criteria):
#         """
#         Feed content to LLM for verification
        
#         Args:
#             content: Scraped text
#             content_description: What is this content supposed to be?
#             quality_criteria: What makes it reliable? (list of strings)
#         """
#         if not content or len(content) < 100:
#             return {'reliable': False, 'reason': 'Content too short', 'confidence': 0}
        
#         # Chunk to 1500 chars
#         chunk = content[:self.chunk_size]
        
#         criteria_str = "\n".join([f"- {c}" for c in quality_criteria])
        
#         prompt = f"""
# You are a content quality analyzer. Evaluate if this content is reliable and substantive.

# Content Type: {content_description}

# Quality Criteria (what makes it reliable):
# {criteria_str}

# Content excerpt (first 1500 chars):
# {chunk}

# Task: Analyze if this is:
# 1. Substantive content matching the description
# 2. Just navigation/headers/metadata
# 3. Partial/incomplete content
# 4. Unrelated content

# Respond ONLY as valid JSON (no markdown, no extra text):
# {{
#   "is_reliable": true/false,
#   "content_type": "substantive|navigation|partial|unrelated|other",
#   "confidence": 0.0-1.0,
#   "key_findings": "What substantive information was found (or why not found)",
#   "reason": "Brief explanation of your decision"
# }}

# Be fair but strict: 
# - Navigation menus, headers = NOT reliable
# - Actual content, data, rules, information = reliable
# - Partial content can still be reliable if substantive
# """
        
#         try:
#             response = self.model.generate_content(prompt)
#             response_text = response.text.strip()
            
#             # Extract JSON
#             start = response_text.find('{')
#             end = response_text.rfind('}') + 1
#             if start < 0 or end <= start:
#                 print(f"    [ERROR] Invalid LLM response format")
#                 return {'reliable': False, 'reason': 'Invalid LLM response', 'confidence': 0}
            
#             result = json.loads(response_text[start:end])
#             return result
#         except json.JSONDecodeError as e:
#             print(f"    [JSON ERROR] {e}")
#             return {'reliable': False, 'reason': f'JSON parse error', 'confidence': 0}
#         except Exception as e:
#             print(f"    [LLM ERROR] {e}")
#             return {'reliable': False, 'reason': f'LLM error: {e}', 'confidence': 0}
    
#     def search_content(self, organization, search_query):
#         """Search for content using DuckDuckGo"""
#         print(f"\n    [SEARCH] DuckDuckGo: {search_query}")
        
#         domain = urlparse(organization).netloc
#         query = f"site:{domain} {search_query}"
        
#         try:
#             ddgs = DDGS(timeout=self.timeout)
#             results = ddgs.text(query, max_results=5)
            
#             search_results = []
#             for result in results:
#                 url = result.get('href')
#                 title = result.get('title', '')
#                 snippet = result.get('body', '')
                
#                 if url:
#                     search_results.append({
#                         'url': url,
#                         'title': title,
#                         'snippet': snippet[:200]
#                     })
#                     print(f"      ✓ {title[:50]}")
            
#             return search_results
#         except Exception as e:
#             print(f"    [SEARCH ERROR] {e}")
#             return []
    
#     def rank_results_by_relevance(self, search_results, content_description):
#         """LLM ranks search results by relevance to content type"""
#         if not search_results:
#             return []
        
#         print(f"    [RANK] Evaluating {len(search_results)} results...")
        
#         results_text = "\n".join([
#             f"{i+1}. {r['title']}\n   URL: {r['url']}\n   Snippet: {r['snippet']}"
#             for i, r in enumerate(search_results[:5])
#         ])
        
#         prompt = f"""
# Rank these search results by relevance to: {content_description}

# Results:
# {results_text}

# Respond ONLY as valid JSON:
# {{
#   "ranking": [
#     {{"position": 1, "url": "URL", "relevance_score": 0.0-1.0, "reason": "why relevant"}}
#   ]
# }}

# Score based on:
# - How well the title/snippet match the content type
# - Likelihood to contain substantive content
# - Avoid pages with just lists or navigation

# Return top 3.
# """
        
#         try:
#             response = self.model.generate_content(prompt)
#             response_text = response.text.strip()
            
#             start = response_text.find('{')
#             end = response_text.rfind('}') + 1
#             if start < 0 or end <= start:
#                 return [(r['url'], 0.5) for r in search_results[:3]]
            
#             result = json.loads(response_text[start:end])
#             ranking = result.get('ranking', [])
            
#             return [(item['url'], item['relevance_score']) for item in ranking]
        
#         except Exception as e:
#             print(f"    [RANK ERROR] {e}")
#             return [(r['url'], 0.5) for r in search_results[:3]]
    
#     def scrape_and_verify(self, url, content_description, quality_criteria, output_dir='scraped_content'):
#         """Scrape URL and verify content"""
#         print(f"\n    [PROCESS] {url}")
        
#         content = self.scrape_content(url)
#         if not content:
#             return None
        
#         # Verify with LLM
#         verification = self.verify_content_reliability(content, content_description, quality_criteria)
        
#         print(f"      Reliable: {verification.get('is_reliable')} (score: {verification.get('confidence', 0):.2f})")
#         print(f"      Type: {verification.get('content_type')}")
        
#         # Save file
#         if not os.path.exists(output_dir):
#             os.makedirs(output_dir)
        
#         # Generate filename
#         domain = urlparse(url).netloc.replace('www.', '').replace('.', '_')
#         content_clean = content_description[:30].lower().replace(' ', '_')
#         confidence_score = verification.get('confidence', 0)
#         filename = f"{output_dir}/{domain}_{content_clean}_{confidence_score:.2f}.txt"
        
#         try:
#             with open(filename, 'w', encoding='utf-8') as f:
#                 f.write(f"URL: {url}\n")
#                 f.write(f"Content Type: {content_description}\n")
#                 f.write(f"Reliability Score: {confidence_score:.2f}\n")
#                 f.write(f"Analysis: {verification.get('content_type')}\n")
#                 f.write(f"Key Findings: {verification.get('key_findings')}\n")
#                 f.write(f"\n{'='*70}\n")
#                 f.write(f"VERIFICATION DETAILS\n")
#                 f.write(f"{'='*70}\n")
#                 f.write(f"Reliable: {verification.get('is_reliable')}\n")
#                 f.write(f"Reason: {verification.get('reason')}\n")
#                 f.write(f"\n{'='*70}\n")
#                 f.write(f"CONTENT\n")
#                 f.write(f"{'='*70}\n\n")
#                 f.write(content)
            
#             print(f"      [SAVED] {filename}")
#             return {
#                 'url': url,
#                 'filename': filename,
#                 'reliable': verification.get('is_reliable'),
#                 'confidence': confidence_score,
#                 'content_length': len(content),
#                 'analysis': verification.get('content_type')
#             }
#         except Exception as e:
#             print(f"      [SAVE ERROR] {e}")
#             return None
    
#     def scrape_with_verification(self, initial_url, content_description, search_keywords, 
#                                   quality_criteria, organization=None, max_urls=3):
#         """
#         Main workflow: Scrape → Verify → Search → Rank → Scrape All
        
#         Args:
#             initial_url: Starting URL to scrape
#             content_description: What content are we looking for? (e.g., "HR Leave Policy")
#             search_keywords: Keywords for search if needed (e.g., "leave policy")
#             quality_criteria: List of what makes content reliable
#             organization: Base URL for site-specific search (defaults to initial_url domain)
#             max_urls: Max URLs to scrape and verify
#         """
        
#         if organization is None:
#             organization = initial_url
        
#         print(f"\n{'='*70}")
#         print(f"Universal Content Scraper with LLM Verification")
#         print(f"{'='*70}")
#         print(f"[TARGET] {content_description}")
#         print(f"[URL] {initial_url}")
#         print(f"[KEYWORDS] {search_keywords}")
        
#         results = []
        
#         # Step 1: Scrape initial URL
#         print(f"\n[STEP 1] Scraping initial content...")
#         initial_content = self.scrape_content(initial_url)
        
#         # Step 2: Verify with LLM
#         print(f"\n[STEP 2] Verifying content with LLM...")
#         verification = self.verify_content_reliability(initial_content, content_description, quality_criteria)
        
#         if verification.get('is_reliable') and verification.get('confidence', 0) > 0.5:
#             print(f"✓ Content is reliable!")
#             result = self.scrape_and_verify(initial_url, content_description, quality_criteria)
#             if result:
#                 results.append(result)
#         else:
#             print(f"✗ Content not reliable ({verification.get('reason')})")
#             print(f"  Reason: {verification.get('key_findings')}")
            
#             # Step 3: Search DuckDuckGo
#             print(f"\n[STEP 3] Searching for relevant content...")
#             search_results = self.search_content(organization, search_keywords)
            
#             if search_results:
#                 # Step 4: Rank with LLM
#                 print(f"\n[STEP 4] Ranking results by relevance...")
#                 ranked = self.rank_results_by_relevance(search_results, content_description)
                
#                 # Step 5: Scrape and verify each
#                 print(f"\n[STEP 5] Scraping and verifying each result...")
#                 for url, score in ranked[:max_urls]:
#                     result = self.scrape_and_verify(url, content_description, quality_criteria)
#                     if result:
#                         results.append(result)
#                         time.sleep(1)  # Polite delay
        
#         # Summary
#         print(f"\n{'='*70}")
#         print(f"SUMMARY")
#         print(f"{'='*70}")
#         reliable_count = sum(1 for r in results if r['reliable'])
#         print(f"✓ Reliable content found: {reliable_count}/{len(results)}")
#         print(f"✓ Total files saved: {len(results)}")
        
#         for r in results:
#             status = "✓" if r['reliable'] else "~"
#             print(f"{status} {os.path.basename(r['filename'])} (score: {r['confidence']:.2f})")
        
#         return results


# def main():
#     api_key = "[REDACTED:api-key]"
#     scraper = UniversalScraperWithLLM(api_key)
    
#     # Example 1: Travel Policy
#     print("\n" + "="*70)
#     print("EXAMPLE 1: Georgia Tech Travel Policy")
#     print("="*70)
    
#     results1 = scraper.scrape_with_verification(
#         initial_url='https://policylibrary.gatech.edu/business-finance/travel',
#         content_description='Travel Policy and Expense Guidelines',
#         search_keywords='travel policy authorization mileage lodging expenses',
#         quality_criteria=[
#             'Contains travel authorization requirements',
#             'Has expense limits and approval processes',
#             'Specifies reimbursement procedures',
#             'Includes per diem and meal allowances',
#             'Actual policy rules, not just navigation'
#         ],
#         organization='https://policylibrary.gatech.edu',
#         max_urls=3
#     )
    
#     time.sleep(2)
    
#     # Example 2: Complete Travel Policy Details
#     print("\n" + "="*70)
#     print("EXAMPLE 2: Complete Travel Policy Details")
#     print("="*70)
    
#     results2 = scraper.scrape_with_verification(
#         initial_url='https://policylibrary.gatech.edu/business-finance/travel',
#         content_description='Complete Travel Policy with All Subsections',
#         search_keywords='travel expenses transportation lodging conference',
#         quality_criteria=[
#             'Contains detailed subsections (air, ground, lodging)',
#             'Has specific dollar amounts and limits',
#             'Includes exceptions and special cases',
#             'Has approval hierarchy and procedures',
#             'Substantive policy content'
#             ],
#             organization='https://policylibrary.gatech.edu',
#             max_urls=1
#     )


# if __name__ == '__main__':
#     main()
