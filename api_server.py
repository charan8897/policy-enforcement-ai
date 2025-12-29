#!/usr/bin/env python3
"""
Policy Enforcement API Server
REST API endpoint for evaluating policy requests against extracted rules.

Workflow:
1. Extract policy to Chroma DB: python3 extract_policy.py extract policy.pdf
2. Generate rules: python3 extract_policy.py extract policy.pdf --rules
3. Start API server: python3 api_server.py
4. Send request to API: POST /api/evaluate with JSON payload

Example:
  curl -X POST http://localhost:5000/api/evaluate \
    -H "Content-Type: application/json" \
    -d '{"request_id": "REQ_001", "grade": "E8", ...}'
"""

import json
import sys
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import evaluation logic
try:
    from extract_policy import RuleEvaluator
except ImportError:
    print("[ERROR] Could not import RuleEvaluator from extract_policy.py")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

# Initialize evaluator
evaluator = None

def initialize_evaluator(rules_file="rules.json", db_path="rules.db"):
    """Initialize the rule evaluator"""
    global evaluator
    try:
        evaluator = RuleEvaluator(rules_file=rules_file, db_path=db_path)
        print(f"[API] Evaluator initialized with rules from {rules_file}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to initialize evaluator: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Policy Enforcement Engine',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/evaluate', methods=['POST'])
def evaluate_request():
    """
    Evaluate a policy request
    
    POST /api/evaluate
    Content-Type: application/json
    
    Request body:
    {
        "request_id": "REQ_001",
        "grade": "E8",
        "destination_country": "United States",
        ...
    }
    
    Response:
    {
        "request_id": "REQ_001",
        "decision": "APPROVE|REJECT",
        "primary_reason": "...",
        "applicable_rules": ["RULE_OVE_001", ...],
        "approvals": [...],
        "violations": [...],
        "timestamp": "2024-01-01T00:00:00"
    }
    """
    
    if not evaluator:
        return jsonify({
            'error': 'Evaluator not initialized',
            'message': 'Rules not loaded. Run: python3 extract_policy.py extract policy.pdf --rules'
        }), 503
    
    try:
        # Get request payload
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'Request body must be valid JSON'
            }), 400
        
        # Validate request_id (required)
        if 'request_id' not in data:
            return jsonify({
                'error': 'Missing field',
                'message': 'request_id is required'
            }), 400
        
        # Evaluate request
        result = evaluator.evaluate(data)
        
        # Add metadata
        result['request_id'] = data.get('request_id')
        result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({
            'error': 'Evaluation failed',
            'message': str(e)
        }), 500


@app.route('/api/rules', methods=['GET'])
def get_rules():
    """Get all extracted rules"""
    if not evaluator:
        return jsonify({
            'error': 'Rules not loaded'
        }), 503
    
    try:
        rules = evaluator.rules
        return jsonify({
            'total_rules': len(rules),
            'rules': rules
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/rules/by-policy/<policy_name>', methods=['GET'])
def get_rules_by_policy(policy_name):
    """Get rules for a specific policy"""
    if not evaluator:
        return jsonify({
            'error': 'Rules not loaded'
        }), 503
    
    try:
        rules = [r for r in evaluator.rules if r.get('policy_name') == policy_name]
        return jsonify({
            'policy_name': policy_name,
            'total_rules': len(rules),
            'rules': rules
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/policies', methods=['GET'])
def get_policies():
    """Get all policies with rule count"""
    if not evaluator:
        return jsonify({
            'error': 'Rules not loaded'
        }), 503
    
    try:
        policies = {}
        for rule in evaluator.rules:
            policy = rule.get('policy_name', 'Unknown')
            if policy not in policies:
                policies[policy] = {
                    'policy_id': rule.get('policy_id'),
                    'rule_count': 0
                }
            policies[policy]['rule_count'] += 1
        
        return jsonify({
            'total_policies': len(policies),
            'policies': policies
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/evaluate/batch', methods=['POST'])
def evaluate_batch():
    """
    Evaluate multiple requests in batch
    
    POST /api/evaluate/batch
    Content-Type: application/json
    
    Request body:
    {
        "requests": [
            {"request_id": "REQ_001", "grade": "E8", ...},
            {"request_id": "REQ_002", "grade": "E6", ...}
        ]
    }
    
    Response:
    {
        "total_requests": 2,
        "results": [
            {"request_id": "REQ_001", "decision": "APPROVE", ...},
            {"request_id": "REQ_002", "decision": "APPROVE", ...}
        ]
    }
    """
    
    if not evaluator:
        return jsonify({
            'error': 'Evaluator not initialized'
        }), 503
    
    try:
        data = request.get_json()
        
        if not data or 'requests' not in data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'requests array is required'
            }), 400
        
        requests_list = data['requests']
        results = []
        
        for req in requests_list:
            if 'request_id' not in req:
                results.append({
                    'request_id': None,
                    'error': 'Missing request_id'
                })
                continue
            
            try:
                result = evaluator.evaluate(req)
                result['request_id'] = req['request_id']
                result['timestamp'] = datetime.now().isoformat()
                results.append(result)
            except Exception as e:
                results.append({
                    'request_id': req['request_id'],
                    'error': str(e)
                })
        
        return jsonify({
            'total_requests': len(requests_list),
            'results': results
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': 'Batch evaluation failed',
            'message': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'Endpoint does not exist',
        'available_endpoints': [
            'GET /health',
            'POST /api/evaluate',
            'GET /api/rules',
            'GET /api/rules/by-policy/<policy_name>',
            'GET /api/policies',
            'POST /api/evaluate/batch'
        ]
    }), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Server error',
        'message': str(error)
    }), 500


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Policy Enforcement API Server')
    parser.add_argument('--rules', default='rules.json', help='Rules JSON file (default: rules.json)')
    parser.add_argument('--db', default='rules.db', help='Database path (default: rules.db)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Policy Enforcement API Server")
    print(f"{'='*60}")
    print(f"[INFO] Initializing...")
    print(f"[INFO] Rules: {args.rules}")
    print(f"[INFO] Database: {args.db}")
    
    # Initialize evaluator
    if not initialize_evaluator(args.rules, args.db):
        sys.exit(1)
    
    print(f"\n[INFO] Starting server on {args.host}:{args.port}")
    print(f"[INFO] Debug mode: {args.debug}")
    print(f"\n[INFO] Available endpoints:")
    print(f"  GET  /health                          Health check")
    print(f"  POST /api/evaluate                    Evaluate single request")
    print(f"  POST /api/evaluate/batch              Evaluate multiple requests")
    print(f"  GET  /api/rules                       Get all rules")
    print(f"  GET  /api/rules/by-policy/<name>     Get rules by policy")
    print(f"  GET  /api/policies                    Get all policies")
    print(f"\n[INFO] Example request:")
    print(f"  curl -X POST http://{args.host}:{args.port}/api/evaluate \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"request_id\": \"REQ_001\", \"grade\": \"E8\", \"destination_country\": \"USA\"}}'")
    print(f"\n{'='*60}\n")
    
    # Start server
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
