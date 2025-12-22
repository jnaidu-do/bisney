from flask import Flask, request, jsonify, render_template_string
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging
import json
import time
from pythonjsonlogger import jsonlogger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Initialize Flask app
app = Flask(__name__)

# Setup JSON logging to stdout
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# Setup OpenTelemetry Tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(ConsoleSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)

# --- PROMETHEUS METRICS ---

bisney_requests_total = Counter(
    'bisney_requests_total',
    'Total requests by tenant and status',
    ['tenant_id', 'status']
)

# NEW: Latency Histogram
bisney_request_duration_seconds = Histogram(
    'bisney_request_duration_seconds',
    'Request duration in seconds',
    ['tenant_id', 'endpoint']
)

bisney_inventory_lag = Gauge(
    'bisney_inventory_lag',
    'Inventory sync lag in seconds',
    ['tenant_id']
)

bisney_cache_hits = Counter(
    'bisney_cache_hits',
    'Cache hit/miss counter',
    ['tenant_id', 'result']
)

# Global state
cart_clicks = 0
favorite_clicks = 0
disaster_mode = False
ddos_mode = False

# Product catalog (Ocean/Beach Theme)
PRODUCTS = [
    {"id": 1, "name": "Giant Conch Shell", "price": 12.50, "icon": "🐚", "desc": "Authentic ocean sound, perfect for decoration"},
    {"id": 2, "name": "Pro Sandcastle Kit", "price": 24.99, "icon": "🏰", "desc": "Includes 5 molds, shovel, and smoothing trowel"},
    {"id": 3, "name": "Inflatable Flamingo", "price": 18.00, "icon": "🦩", "desc": "Oversized pool float for maximum relaxation"},
    {"id": 4, "name": "Snorkel & Mask Set", "price": 35.00, "icon": "🤿", "desc": "Anti-fog tempered glass with dry-top snorkel"},
    {"id": 5, "name": "Beach Volleyball", "price": 15.50, "icon": "🏐", "desc": "Soft-touch synthetic leather, water resistant"},
    {"id": 6, "name": "Sunscreen - SPF 50", "price": 9.99, "icon": "🧴", "desc": "Reef-safe formula, 80 minutes water resistance"},
]

# HTML UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bisney - Premium Beach Gear</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #F7F9FC; min-height: 100vh; }
        .header { background: #FFFFFF; padding: 20px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #E5E8ED; }
        .nav { max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.8em; font-weight: 700; color: #0069FF; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px; }
        .logo::before { content: '🌊'; font-size: 1.2em; }
        .nav-links { display: flex; gap: 30px; align-items: center; }
        .nav-links a { color: #4A5568; text-decoration: none; font-size: 0.95em; font-weight: 500; transition: color 0.2s; }
        .nav-links a:hover { color: #0069FF; }
        .hero { background: linear-gradient(135deg, #0069FF 0%, #0080FF 50%, #00A6FF 100%); color: white; padding: 80px 20px; text-align: center; position: relative; overflow: hidden; }
        .hero::before { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(circle at 20% 50%, rgba(255,255,255,0.1) 0%, transparent 50%); }
        .hero h1 { font-size: 3em; font-weight: 700; margin-bottom: 15px; position: relative; z-index: 1; }
        .hero p { font-size: 1.3em; opacity: 0.95; position: relative; z-index: 1; margin-bottom: 15px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 30px; }
        .product-card { background: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); transition: transform 0.2s, box-shadow 0.2s; border: 1px solid #E5E8ED; }
        .product-card:hover { transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,105,255,0.12); border-color: #0069FF; }
        .product-image { background: linear-gradient(135deg, #E0F2FF 0%, #B3DDFF 100%); height: 180px; display: flex; align-items: center; justify-content: center; font-size: 4em; position: relative; }
        .product-info { padding: 20px; }
        .product-name { font-size: 1.25em; font-weight: 600; color: #1A202C; margin-bottom: 8px; }
        .product-desc { color: #718096; font-size: 0.9em; margin-bottom: 15px; line-height: 1.5; }
        .product-price { font-size: 1.8em; font-weight: 700; color: #0069FF; margin-bottom: 15px; }
        .product-price::before { content: '$'; font-size: 0.7em; vertical-align: super; }
        .product-actions { display: flex; gap: 10px; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-size: 0.95em; flex: 1; }
        .btn-cart { background: #0069FF; color: white; }
        .btn-cart:hover { background: #0057D9; box-shadow: 0 4px 12px rgba(0,105,255,0.3); }
        .btn-favorite { background: #F7F9FC; color: #4A5568; border: 1px solid #E5E8ED; flex: 0 0 auto; padding: 12px 16px; }
        .btn-favorite:hover { background: #EDF2F7; border-color: #CBD5E0; }
        .btn-favorite.active { background: #FEE; color: #E53E3E; border-color: #E53E3E; }
        .toast { position: fixed; top: 80px; right: 20px; max-width: 350px; background: white; padding: 16px 20px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); display: none; animation: slideIn 0.3s ease; z-index: 1000; border: 1px solid #E5E8ED; }
        .toast.show { display: block; }
        @keyframes slideIn { from { transform: translateX(400px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .toast.success { border-left: 4px solid #48BB78; }
        .toast.error { border-left: 4px solid #F56565; }
        .toast-title { font-weight: 600; margin-bottom: 4px; color: #1A202C; }
        .toast-message { font-size: 0.9em; color: #718096; }
        .admin-controls { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 10px; }
        .admin-btn { padding: 12px 16px; cursor: pointer; font-size: 0.85em; font-weight: 600; background: white; color: #4A5568; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.2s; min-width: 140px; border: 1px solid #E5E8ED; border-radius: 6px; }
        .admin-btn:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); transform: translateY(-2px); border-color: #CBD5E0; }
        .admin-btn.active { background: #0069FF; color: white; border-color: #0069FF; }
        .admin-btn.ddos.active { background: #E53E3E; border-color: #E53E3E; }
        .footer { background: white; padding: 40px 20px; text-align: center; color: #718096; font-size: 0.9em; margin-top: 60px; border-top: 1px solid #E5E8ED; }
        .footer a { color: #0069FF; text-decoration: none; font-weight: 500 }
    </style>
</head>
<body>
    <div class="header">
        <div class="nav">
            <div class="logo">Bisney</div>
            <div class="nav-links"><a href="#">Shop</a><a href="#">Rentals</a><a href="#">About Us</a><a href="/metrics">Metrics</a></div>
        </div>
    </div>
    <div class="hero"><h1>Premium Ocean Essentials</h1><p>Build the perfect sandcastle and relax in style</p></div>
    <div class="container">
        <div class="products-grid">
            {% for product in products %}
            <div class="product-card">
                <div class="product-image">{{ product.icon }}</div>
                <div class="product-info">
                    <div class="product-name">{{ product.name }}</div>
                    <div class="product-desc">{{ product.desc }}</div>
                    <div class="product-price">{{ "%.2f"|format(product.price) }}</div>
                    <div class="product-actions">
                        <button class="btn btn-cart" onclick="addToCart({{ product.id }}, '{{ product.name }}')">Add to Cart</button>
                        <button class="btn btn-favorite" onclick="toggleFavorite({{ product.id }})" id="fav-{{ product.id }}">❤️</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    <div id="toast" class="toast"><div class="toast-title" id="toastTitle"></div><div class="toast-message" id="toastMessage"></div></div>
    <div class="admin-controls">
        <button class="admin-btn" id="disasterBtn" onclick="toggleDisaster()">🔥 Load Test: OFF</button>
        <button class="admin-btn ddos" id="ddosBtn" onclick="toggleDDoS()">DDoS: OFF</button>
    </div>
    <div class="footer"><p>System Health: <a href="/metrics">View Metrics</a> | Powered by Bisney</p></div>
    <script>
        function showToast(title, message, type) {
            const toast = document.getElementById('toast');
            toast.className = 'toast show ' + type;
            document.getElementById('toastTitle').textContent = title;
            document.getElementById('toastMessage').textContent = message;
            setTimeout(() => { toast.classList.remove('show'); }, 3000);
        }
        async function addToCart(productId, productName) {
            try {
                const response = await fetch('/cart', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({product_id: productId, product_name: productName})
                });
                const data = await response.json();
                if (response.ok) showToast('Added to Cart', `${productName} added successfully!`, 'success');
                else showToast('Payment Error', data.error || 'Please try again', 'error');
            } catch (error) { showToast('Error', 'Unable to add to cart', 'error'); }
        }
        async function toggleFavorite(productId) {
            const btn = document.getElementById('fav-' + productId);
            btn.classList.toggle('active');
            try {
                const response = await fetch('/favorite', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({product_id: productId})
                });
                if (response.ok) showToast('Favorites Updated', `Product updated`, 'success');
                else btn.classList.toggle('active');
            } catch (error) { btn.classList.toggle('active'); }
        }
        async function toggleDisaster() {
            try {
                const response = await fetch('/disaster', { method: 'POST' });
                const data = await response.json();
                const btn = document.getElementById('disasterBtn');
                if (data.disaster_mode) { btn.textContent = '🔥 Load Test: ON'; btn.classList.add('active'); }
                else { btn.textContent = '🔥 Load Test: OFF'; btn.classList.remove('active'); }
            } catch (e) {}
        }
        let ddosInterval = null;
        async function toggleDDoS() {
            try {
                const response = await fetch('/ddos', { method: 'POST' });
                const data = await response.json();
                const btn = document.getElementById('ddosBtn');
                if (data.ddos_mode) {
                    btn.textContent = 'DDoS: ON'; btn.classList.add('active');
                    showToast('DDoS Mode', 'Attack simulation active!', 'error');
                    ddosInterval = setInterval(async () => {
                        try { await fetch(Math.random() > 0.5 ? '/cart' : '/favorite', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({product_id: 1, product_name: 'DDoS'}) }); } catch (e) {}
                    }, 100);
                } else {
                    btn.textContent = 'DDoS: OFF'; btn.classList.remove('active');
                    showToast('DDoS Mode', 'Attack simulation stopped', 'success');
                    if (ddosInterval) { clearInterval(ddosInterval); ddosInterval = null; }
                }
            } catch (e) {}
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the UI"""
    return render_template_string(HTML_TEMPLATE, products=PRODUCTS)

@app.route('/cart', methods=['POST'])
def cart_checkout():
    """Handle cart checkout with latency tracking"""
    global cart_clicks
    cart_clicks += 1
    
    data = request.get_json() or {}
    product_name = data.get('product_name', 'Unknown Product')
    tenant_id = 'merch'
    
    # NEW: Start timer for latency metric
    with bisney_request_duration_seconds.labels(tenant_id=tenant_id, endpoint='/cart').time():
        
        # Start OpenTelemetry span
        with tracer.start_as_current_span("checkout_flow") as span:
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("click_count", cart_clicks)
            span.set_attribute("product", product_name)
            
            # Every 3rd click fails
            if cart_clicks % 3 == 0:
                logger.error("Payment processing failed", extra={"event": "payment_failure", "tenant_id": tenant_id})
                span.set_status(Status(StatusCode.ERROR, "Payment processing failed"))
                bisney_requests_total.labels(tenant_id=tenant_id, status='error').inc()
                
                # Update inventory lag
                if disaster_mode:
                    bisney_inventory_lag.labels(tenant_id=tenant_id).set(600)
                else:
                    bisney_inventory_lag.labels(tenant_id=tenant_id).set(120)
                
                return jsonify({"error": "Payment gateway timeout", "clicks": cart_clicks}), 500
            else:
                logger.info("Cart checkout successful", extra={"event": "checkout_success", "tenant_id": tenant_id})
                span.set_status(Status(StatusCode.OK))
                bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
                
                if disaster_mode:
                    bisney_inventory_lag.labels(tenant_id=tenant_id).set(600)
                else:
                    bisney_inventory_lag.labels(tenant_id=tenant_id).set(15)
                
                return jsonify({"message": "Checkout successful", "clicks": cart_clicks}), 200

@app.route('/favorite', methods=['POST'])
def favorite_product():
    """Handle favorite with latency tracking"""
    global favorite_clicks
    favorite_clicks += 1
    
    data = request.get_json() or {}
    product_id = data.get('product_id', 0)
    tenant_id = 'favorites'
    
    # NEW: Start timer for latency metric
    with bisney_request_duration_seconds.labels(tenant_id=tenant_id, endpoint='/favorite').time():
    
        # Start OpenTelemetry span
        with tracer.start_as_current_span("favorite_toggle") as span:
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("product_id", product_id)
            
            # Every 2nd click is a cache miss (SLOW)
            if favorite_clicks % 2 == 0:
                logger.warning("Favorite cache miss", extra={"event": "cache_miss", "tenant_id": tenant_id})
                span.set_attribute("cache_result", "miss")
                bisney_cache_hits.labels(tenant_id=tenant_id, result='miss').inc()
                
                time.sleep(0.8) # Simulate slow DB
                duration = 0.8
            else:
                logger.info("Favorite cache hit", extra={"event": "cache_hit", "tenant_id": tenant_id})
                span.set_attribute("cache_result", "hit")
                bisney_cache_hits.labels(tenant_id=tenant_id, result='hit').inc()
                
                time.sleep(0.05) # Simulate fast cache
                duration = 0.05
            
            span.set_status(Status(StatusCode.OK))
            bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
            
            return jsonify({"message": "Favorite toggled", "duration": duration}), 200

@app.route('/disaster', methods=['POST'])
def toggle_disaster():
    global disaster_mode
    disaster_mode = not disaster_mode
    logger.info("Disaster mode toggled", extra={"event": "disaster_mode_toggle", "disaster_mode": disaster_mode})
    return jsonify({"disaster_mode": disaster_mode}), 200

@app.route('/ddos', methods=['POST'])
def toggle_ddos():
    global ddos_mode
    ddos_mode = not ddos_mode
    logger.warning("DDoS mode toggled", extra={"event": "ddos_mode_toggle", "ddos_mode": ddos_mode})
    return jsonify({"ddos_mode": ddos_mode}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    logger.info("Bisney application starting", extra={"event": "app_startup", "port": 5001})
    # Initialize buckets
    for tenant in ['merch', 'favorites']:
        bisney_requests_total.labels(tenant_id=tenant, status='success').inc(0)
    app.run(host='0.0.0.0', port=5001, debug=False)