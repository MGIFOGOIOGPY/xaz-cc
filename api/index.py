from flask import Flask, render_template, request, jsonify, session
import sqlite3
import re
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'xaz_cc_secret_key_2024_ropd'
app.config['DATABASE'] = 'cards_database.db'

# Initialize database
def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_data TEXT NOT NULL,
            frame_number INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_ip TEXT,
            user_agent TEXT
        )
    ''')
    
    # Initialize 100 empty frames
    for i in range(1, 101):
        c.execute('SELECT COUNT(*) FROM cards WHERE frame_number = ?', (i,))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO cards (card_data, frame_number) VALUES (?, ?)', ('', i))
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def extract_card_data(text):
    """استخراج بيانات البطاقة من النص بأشكال مختلفة"""
    # أنماط متعددة لاستخراج البطاقات
    patterns = [
        r'(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4})',
        r'Card:\s*(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4})',
        r'🔹\s*(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4})',
        r'(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4}.*?3D_AUTHENTICATION)',
        r'(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4}.*?Approved)',
        r'(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4}.*?✅)',
        r'(\d{15,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            if isinstance(matches[0], tuple):
                return list(matches[0])
            else:
                parts = matches[0].split('|')
                if len(parts) >= 4:
                    return parts[0:4]
    
    return None

def format_card_display(card_data, original_text=""):
    """تنسيق عرض البطاقة بشكل جميل"""
    if not card_data or len(card_data) < 4:
        return "🕳️ Empty Frame"
    
    card_number = card_data[0]
    month = card_data[1]
    year = card_data[2]
    cvv = card_data[3]
    
    # تحديد نوع البطاقة
    if card_number.startswith('4'):
        card_type = "VISA"
        icon = "💳"
        gradient = "linear-gradient(135deg, #1a237e, #3949ab)"
        badge_color = "#1976d2"
    elif card_number.startswith('5'):
        card_type = "MASTERCARD"
        icon = "💳"
        gradient = "linear-gradient(135deg, #ff6f00, #ffa000)"
        badge_color = "#f57c00"
    elif card_number.startswith('3'):
        card_type = "AMEX"
        icon = "💳"
        gradient = "linear-gradient(135deg, #00695c, #004d40)"
        badge_color = "#00796b"
    elif card_number.startswith('6'):
        card_type = "DISCOVER"
        icon = "💳"
        gradient = "linear-gradient(135deg, #e65100, #ff6f00)"
        badge_color = "#e64a19"
    else:
        card_type = "UNKNOWN"
        icon = "💳"
        gradient = "linear-gradient(135deg, #37474f, #546e7a)"
        badge_color = "#455a64"
    
    # تنسيق السنة
    if len(year) == 2:
        year = f"20{year}"
    
    # إنشاء رمز البطاقة
    card_display = f"""
    <div class="card-preview" style="background: {gradient};">
        <div class="card-chip">🟡</div>
        <div class="card-number">•••• •••• •••• {card_number[-4:]}</div>
        <div class="card-type">{card_type}</div>
    </div>
    """
    
    # المعلومات التفصيلية
    card_info = f"""
    <div class="card-details">
        <div class="detail-item">
            <span class="detail-icon">🎯</span>
            <span class="detail-label">Card Number:</span>
            <span class="detail-value">{card_number[:6]}******{card_number[-4:]}</span>
        </div>
        <div class="detail-item">
            <span class="detail-icon">📅</span>
            <span class="detail-label">Expiry Date:</span>
            <span class="detail-value">{month}/{year}</span>
        </div>
        <div class="detail-item">
            <span class="detail-icon">🔐</span>
            <span class="detail-label">CVV:</span>
            <span class="detail-value">{cvv}</span>
        </div>
        <div class="detail-item">
            <span class="detail-icon">🏦</span>
            <span class="detail-label">Type:</span>
            <span class="detail-value">{card_type} - CREDIT</span>
        </div>
        <div class="detail-item">
            <span class="detail-icon">🌍</span>
            <span class="detail-label">Status:</span>
            <span class="detail-value approved">3D SECURE VERIFIED</span>
        </div>
        <div class="detail-item">
            <span class="detail-icon">⏰</span>
            <span class="detail-label">Added:</span>
            <span class="detail-value">{datetime.now().strftime('%H:%M:%S')}</span>
        </div>
    </div>
    
    <div class="signature">
        <span class="verified-badge">✅ VERIFIED</span>
        <span class="author">by: @R_O_P_D</span>
    </div>
    """
    
    return card_display + card_info

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    conn = get_db_connection()
    cards = conn.execute('''
        SELECT * FROM cards ORDER BY frame_number
    ''').fetchall()
    
    # إحصائيات
    total_filled = conn.execute('SELECT COUNT(*) FROM cards WHERE card_data != ""').fetchone()[0]
    conn.close()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚀 {XAZ >>{CC • Premium Card Marketplace</title>
        <meta name="description" content="Premium Card Marketplace • Verified Cards • Instant Delivery • Secure Transactions">
        <meta property="og:title" content="{XAZ >>{CC • Premium Card Shop">
        <meta property="og:description" content="Exclusive Card Marketplace • 100% Verified • Instant Access">
        <meta property="og:image" content="https://i.imgur.com/cc_preview.png">
        <meta property="og:url" content="xaz-cc.vercel.app/">
        <meta name="twitter:card" content="summary_large_image">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            :root {
                --primary: #00ff88;
                --secondary: #0099ff;
                --accent: #ff0066;
                --dark: #0a0a0a;
                --darker: #050505;
                --light: #ffffff;
                --gray: #2a2a2a;
                --glow: 0 0 20px rgba(0, 255, 136, 0.3);
            }

            body {
                font-family: 'Rajdhani', sans-serif;
                background: var(--darker);
                color: var(--light);
                min-height: 100vh;
                overflow-x: hidden;
                background-image: 
                    radial-gradient(circle at 10% 20%, rgba(0, 255, 136, 0.05) 0%, transparent 20%),
                    radial-gradient(circle at 90% 80%, rgba(0, 153, 255, 0.05) 0%, transparent 20%),
                    radial-gradient(circle at 50% 50%, rgba(255, 0, 102, 0.03) 0%, transparent 50%);
            }

            .cyber-border {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                pointer-events: none;
                z-index: 1000;
                border: 2px solid var(--primary);
                margin: 10px;
                box-shadow: var(--glow);
                animation: borderPulse 4s ease-in-out infinite;
            }

            @keyframes borderPulse {
                0%, 100% { opacity: 0.7; }
                50% { opacity: 0.3; }
            }

            .container {
                max-width: 1800px;
                margin: 0 auto;
                padding: 30px;
                position: relative;
                z-index: 1;
            }

            .header {
                text-align: center;
                padding: 50px 0;
                margin-bottom: 50px;
                position: relative;
            }

            .cyber-glitch {
                font-family: 'Orbitron', monospace;
                font-size: 5em;
                font-weight: 900;
                background: linear-gradient(45deg, var(--primary), var(--secondary), var(--accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-shadow: 
                    0 0 30px var(--primary),
                    0 0 60px var(--secondary),
                    0 0 90px var(--accent);
                animation: glitch 3s infinite;
                margin-bottom: 20px;
            }

            @keyframes glitch {
                0%, 100% { transform: translate(0); }
                25% { transform: translate(-2px, 2px); }
                50% { transform: translate(2px, -2px); }
                75% { transform: translate(-2px, -2px); }
            }

            .subtitle {
                font-size: 1.4em;
                color: var(--primary);
                font-weight: 600;
                letter-spacing: 3px;
                text-transform: uppercase;
                margin-bottom: 30px;
            }

            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 50px;
            }

            .stat-card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 255, 136, 0.2);
                border-radius: 15px;
                padding: 25px;
                text-align: center;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }

            .stat-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(0, 255, 136, 0.1), transparent);
                transition: left 0.5s ease;
            }

            .stat-card:hover::before {
                left: 100%;
            }

            .stat-card:hover {
                transform: translateY(-5px);
                border-color: var(--primary);
                box-shadow: var(--glow);
            }

            .stat-number {
                font-size: 2.5em;
                font-weight: 700;
                color: var(--primary);
                margin-bottom: 10px;
            }

            .stat-label {
                font-size: 0.9em;
                color: #8892b0;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .frames-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
                gap: 25px;
                margin-top: 40px;
            }

            .frame {
                background: rgba(255, 255, 255, 0.03);
                backdrop-filter: blur(15px);
                border: 1px solid rgba(0, 255, 136, 0.1);
                border-radius: 20px;
                padding: 25px;
                min-height: 320px;
                transition: all 0.4s ease;
                position: relative;
                overflow: hidden;
            }

            .frame::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
                transform: scaleX(0);
                transition: transform 0.3s ease;
            }

            .frame:hover::before {
                transform: scaleX(1);
            }

            .frame:hover {
                transform: translateY(-8px) scale(1.02);
                border-color: var(--primary);
                box-shadow: 
                    0 10px 40px rgba(0, 255, 136, 0.2),
                    0 0 0 1px rgba(0, 255, 136, 0.1);
            }

            .frame-number {
                position: absolute;
                top: 15px;
                right: 20px;
                background: rgba(0, 255, 136, 0.1);
                color: var(--primary);
                padding: 8px 15px;
                border-radius: 20px;
                font-size: 0.8em;
                font-weight: 600;
                border: 1px solid rgba(0, 255, 136, 0.3);
            }

            .frame-content {
                margin-top: 40px;
            }

            .empty-frame {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 200px;
                color: #556;
                text-align: center;
            }

            .empty-icon {
                font-size: 3em;
                margin-bottom: 15px;
                opacity: 0.5;
            }

            .empty-text {
                font-size: 1.1em;
                color: #667;
                font-style: italic;
            }

            /* Card Preview Styles */
            .card-preview {
                background: linear-gradient(135deg, #1a237e, #3949ab);
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 20px;
                position: relative;
                height: 120px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
            }

            .card-chip {
                font-size: 2em;
            }

            .card-number {
                font-family: 'Courier New', monospace;
                font-size: 1.2em;
                font-weight: bold;
                letter-spacing: 2px;
                color: white;
            }

            .card-type {
                position: absolute;
                bottom: 15px;
                right: 20px;
                color: white;
                font-weight: bold;
                font-size: 0.9em;
            }

            /* Card Details Styles */
            .card-details {
                margin-bottom: 20px;
            }

            .detail-item {
                display: flex;
                align-items: center;
                margin-bottom: 8px;
                padding: 5px 0;
            }

            .detail-icon {
                margin-right: 10px;
                font-size: 1em;
            }

            .detail-label {
                flex: 1;
                font-size: 0.85em;
                color: #8892b0;
                font-weight: 500;
            }

            .detail-value {
                font-size: 0.85em;
                font-weight: 600;
                color: var(--light);
            }

            .approved {
                color: var(--primary) !important;
                font-weight: 700;
            }

            .signature {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 20px;
                padding-top: 15px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }

            .verified-badge {
                background: rgba(0, 255, 136, 0.1);
                color: var(--primary);
                padding: 5px 10px;
                border-radius: 10px;
                font-size: 0.8em;
                font-weight: 600;
                border: 1px solid rgba(0, 255, 136, 0.3);
            }

            .author {
                color: var(--secondary);
                font-size: 0.8em;
                font-weight: 600;
            }

            .footer {
                text-align: center;
                margin-top: 80px;
                padding: 40px 0;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                color: #667;
                font-size: 0.9em;
            }

            .cyber-grid {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-image: 
                    linear-gradient(rgba(0, 255, 136, 0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0, 255, 136, 0.03) 1px, transparent 1px);
                background-size: 50px 50px;
                pointer-events: none;
                z-index: 0;
            }

            /* Animations */
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }

            .floating {
                animation: float 6s ease-in-out infinite;
            }

            /* Responsive */
            @media (max-width: 768px) {
                .cyber-glitch { font-size: 3em; }
                .frames-container { grid-template-columns: 1fr; }
                .container { padding: 15px; }
            }
        </style>
    </head>
    <body>
        <div class="cyber-grid"></div>
        <div class="cyber-border"></div>
        
        <div class="container">
            <div class="header">
                <div class="cyber-glitch floating">{XAZ >>{CC}</div>
                <div class="subtitle">PREMIUM CARD MARKETPLACE • INSTANT DELIVERY • SECURE TRANSACTIONS</div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">100</div>
                        <div class="stat-label">Total Slots</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">""" + str(total_filled) + """</div>
                        <div class="stat-label">Active Cards</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">""" + str(100 - total_filled) + """</div>
                        <div class="stat-label">Available Slots</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">24/7</div>
                        <div class="stat-label">Live Support</div>
                    </div>
                </div>
            </div>

            <div class="frames-container" id="framesContainer">
    """
    
    # إضافة الإطارات
    for card in cards:
        frame_class = "frame floating"
        card_data = json.loads(card['card_data']) if card['card_data'] else None
        
        html_content += f"""
                <div class="{frame_class}">
                    <div class="frame-number">SLOT #{card['frame_number']}</div>
                    <div class="frame-content">
        """
        
        if card_data:
            html_content += format_card_display(card_data)
        else:
            html_content += """
                        <div class="empty-frame">
                            <div class="empty-icon">🕳️</div>
                            <div class="empty-text">Awaiting Premium Card...</div>
                        </div>
            """
        
        html_content += """
                    </div>
                </div>
        """
    
    html_content += """
            </div>

            <div class="footer">
                <p>🔒 SECURE • ⚡ INSTANT • 💎 PREMIUM • 🌐 GLOBAL</p>
                <p>© 2025 {XAZ >>{CC • Premium Card Marketplace • by: @R_O_P_D</p>
            </div>
        </div>

        <script>
            // تأثيرات تفاعلية
            document.addEventListener('DOMContentLoaded', function() {
                const frames = document.querySelectorAll('.frame');
                
                // تأثير ظهور متدرج
                frames.forEach((frame, index) => {
                    frame.style.opacity = '0';
                    frame.style.transform = 'translateY(50px)';
                    
                    setTimeout(() => {
                        frame.style.transition = 'all 0.6s ease';
                        frame.style.opacity = '1';
                        frame.style.transform = 'translateY(0)';
                    }, index * 100);
                });

                // تأثير تحويم على البطاقات
                frames.forEach(frame => {
                    frame.addEventListener('mouseenter', function() {
                        this.style.zIndex = '10';
                    });
                    
                    frame.addEventListener('mouseleave', function() {
                        this.style.zIndex = '1';
                    });
                });

                // تحديث تلقائي كل 10 ثواني
                setInterval(() => {
                    fetch('/api/get_cards')
                        .then(response => response.json())
                        .then(data => {
                            console.log('Auto-refresh completed');
                        })
                        .catch(err => console.log('Refresh error:', err));
                }, 10000);
            });

            // تأثير كتابة للنص
            const glitchText = document.querySelector('.cyber-glitch');
            if (glitchText) {
                setInterval(() => {
                    glitchText.style.animation = 'none';
                    setTimeout(() => {
                        glitchText.style.animation = 'glitch 3s infinite';
                    }, 10);
                }, 7000);
            }
        </script>
    </body>
    </html>
    """
    
    return html_content

@app.route('/api/add_card', methods=['POST'])
def add_card():
    """API لإضافة بطاقة جديدة"""
    secret_key = request.headers.get('X-Secret-Key')
    data = request.get_json()
    
    # التحقق من المفتاح السري
    if secret_key != 'XAZ_CC_SECRET_2024':
        return jsonify({'status': 'error', 'message': 'Invalid secret key'}), 401
    
    if not data or 'card_data' not in data:
        return jsonify({'status': 'error', 'message': 'No card data provided'}), 400
    
    card_text = data['card_data']
    card_data = extract_card_data(card_text)
    
    if not card_data:
        return jsonify({'status': 'error', 'message': 'Invalid card format'}), 400
    
    conn = get_db_connection()
    
    # البحث عن أول إطار فارغ
    empty_frame = conn.execute('''
        SELECT frame_number FROM cards 
        WHERE card_data = '' OR card_data IS NULL 
        ORDER BY frame_number LIMIT 1
    ''').fetchone()
    
    if not empty_frame:
        return jsonify({'status': 'error', 'message': 'All frames are full'}), 400
    
    frame_number = empty_frame['frame_number']
    
    # تحديث البطاقة في الإطار الفارغ
    conn.execute('''
        UPDATE cards SET card_data = ?, status = 'active', 
        created_at = CURRENT_TIMESTAMP, source_ip = ?, user_agent = ?
        WHERE frame_number = ?
    ''', (json.dumps(card_data), request.remote_addr, request.headers.get('User-Agent'), frame_number))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success', 
        'message': 'Card added successfully',
        'frame_number': frame_number,
        'formatted_card': format_card_display(card_data, card_text)
    })

@app.route('/api/get_cards')
def get_cards():
    """الحصول على جميع البطاقات"""
    conn = get_db_connection()
    cards = conn.execute('''
        SELECT * FROM cards ORDER BY frame_number
    ''').fetchall()
    conn.close()
    
    cards_list = []
    for card in cards:
        card_data = json.loads(card['card_data']) if card['card_data'] else None
        cards_list.append({
            'frame_number': card['frame_number'],
            'card_data': card_data,
            'formatted_display': format_card_display(card_data) if card_data else "Empty Frame",
            'status': card['status'],
            'created_at': card['created_at']
        })
    
    return jsonify({'cards': cards_list})

@app.route('/api/clear_frame/<int:frame_number>', methods=['POST'])
def clear_frame(frame_number):
    """تفريغ إطار معين"""
    if frame_number < 1 or frame_number > 100:
        return jsonify({'status': 'error', 'message': 'Invalid frame number'}), 400
    
    conn = get_db_connection()
    conn.execute('UPDATE cards SET card_data = "", status = "empty" WHERE frame_number = ?', (frame_number,))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': f'Frame {frame_number} cleared'})

@app.route('/api/stats')
def get_stats():
    """إحصائيات الموقع"""
    conn = get_db_connection()
    total_cards = conn.execute('SELECT COUNT(*) FROM cards WHERE card_data != ""').fetchone()[0]
    empty_frames = 100 - total_cards
    conn.close()
    
    return jsonify({
        'total_frames': 100,
        'filled_frames': total_cards,
        'empty_frames': empty_frames,
        'last_update': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
