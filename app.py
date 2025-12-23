from flask import Flask, request, jsonify, render_template_string
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging
import json
import time
import random
import threading
import requests
from pythonjsonlogger import jsonlogger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Initialize Flask app
app = Flask(__name__)

# --- CONFIGURATION & STATE ---
SIMULATION_CONFIG = {
    "ddos_mode": False,
    "latency_mode": False
}

# --- LOGGING SETUP ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# --- TRACING SETUP ---
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

# Latency Histogram (Buckets optimized for visualizing the 2s-5s latency mode)
bisney_request_duration_seconds = Histogram(
    'bisney_request_duration_seconds',
    'Request duration in seconds',
    ['tenant_id', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0]
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

# Product catalog
PRODUCTS = [
    {"id": 1, "name": "Giant Conch Shell", "price": 12.50, "icon": "🐚", "desc": "Authentic ocean sound"},
    {"id": 2, "name": "Pro Sandcastle Kit", "price": 24.99, "icon": "🏰", "desc": "Includes 5 molds and shovel"},
    {"id": 3, "name": "Inflatable Flamingo", "price": 18.00, "icon": "🦩", "desc": "Oversized pool float"},
    {"id": 4, "name": "Snorkel & Mask Set", "price": 35.00, "icon": "🤿", "desc": "Anti-fog tempered glass"},
    {"id": 5, "name": "Beach Volleyball", "price": 15.50, "icon": "🏐", "desc": "Soft-touch synthetic leather"},
    {"id": 6, "name": "Sunscreen - SPF 50", "price": 9.99, "icon": "🧴", "desc": "Reef-safe formula"},
]

# --- HELPER FUNCTIONS ---

def inject_latency():
    """Injects artificial latency based on the current mode."""
    if SIMULATION_CONFIG["latency_mode"]:
        # Simulate heavy DB load or lock (2s to 5s)
        time.sleep(random.uniform(2.0, 5.0))
    else:
        # Normal operation (very fast)
        time.sleep(random.uniform(0.01, 0.05))

# --- NUCLEAR DDOS GENERATOR ---
def background_ddos_generator():
    """
    Optimized attacker using Session pooling.
    Spams BOTH /cart and /favorite endpoints.
    """
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    session.mount('http://', adapter)
    
    base_url = 'http://127.0.0.1:5001'
    
    while True:
        if SIMULATION_CONFIG["ddos_mode"]:
            try:
                # Randomly attack Cart (DB write) or Favorite (Cache read)
                if random.random() > 0.5:
                    session.post(f'{base_url}/cart', json={"product_name": "DDoS-Bot", "tenant": "attacker"}, timeout=0.1)
                else:
                    session.post(f'{base_url}/favorite', json={"product_id": 999, "tenant": "attacker"}, timeout=0.1)
            except Exception:
                pass
        else:
            time.sleep(1.0) # Sleep while idle

# Start 50 concurrent attacker threads (The "Botnet")
for _ in range(50):
    threading.Thread(target=background_ddos_generator, daemon=True).start()

# --- HTML UI ---
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
        
        /* Nav Icons with Badges */
        .nav-icon { position: relative; font-size: 1.2em; cursor: pointer; }
        .badge { 
            position: absolute; top: -8px; right: -8px; 
            background: #E53E3E; color: white; 
            font-size: 0.6em; font-weight: bold; 
            padding: 2px 6px; border-radius: 10px; 
            min-width: 18px; text-align: center;
            opacity: 0; transition: opacity 0.2s;
        }
        .badge.visible { opacity: 1; }

        .hero { background: linear-gradient(135deg, #0069FF 0%, #0080FF 50%, #00A6FF 100%); color: white; padding: 80px 20px; text-align: center; position: relative; overflow: hidden; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 30px; }
        .product-card { background: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); transition: transform 0.2s; border: 1px solid #E5E8ED; }
        .product-card:hover { transform: translateY(-4px); border-color: #0069FF; }
        .product-image { background: linear-gradient(135deg, #E0F2FF 0%, #B3DDFF 100%); height: 180px; display: flex; align-items: center; justify-content: center; font-size: 4em; }
        .product-info { padding: 20px; }
        .product-name { font-size: 1.25em; font-weight: 600; color: #1A202C; margin-bottom: 8px; }
        .product-desc { color: #718096; font-size: 0.9em; margin-bottom: 15px; line-height: 1.5; }
        .product-price { font-size: 1.8em; font-weight: 700; color: #0069FF; margin-bottom: 15px; }
        .product-price::before { content: '$'; font-size: 0.7em; vertical-align: super; }
        .product-actions { display: flex; gap: 10px; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-size: 0.95em; flex: 1; }
        .btn-cart { background: #0069FF; color: white; }
        .btn-cart:hover { background: #0057D9; }
        .btn-favorite { background: #F7F9FC; color: #4A5568; border: 1px solid #E5E8ED; flex: 0 0 auto; padding: 12px 16px; }
        .btn-favorite:hover { background: #EDF2F7; }
        .btn-favorite.active { background: #FEE; color: #E53E3E; border-color: #E53E3E; }
        
        .toast { position: fixed; top: 80px; right: 20px; max-width: 350px; background: white; padding: 16px 20px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); display: none; animation: slideIn 0.3s ease; z-index: 1000; border: 1px solid #E5E8ED; }
        .toast.show { display: block; }
        .toast.success { border-left: 4px solid #48BB78; }
        .toast.error { border-left: 4px solid #F56565; }
        @keyframes slideIn { from { transform: translateX(400px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        
        .admin-controls { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 10px; }
        .admin-btn { padding: 12px 16px; cursor: pointer; font-size: 0.85em; font-weight: 600; background: white; color: #4A5568; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.2s; min-width: 160px; border: 1px solid #E5E8ED; border-radius: 6px; text-align: left; display: flex; justify-content: space-between; align-items: center; }
        .admin-btn:hover { transform: translateY(-2px); }
        .admin-btn.active { background: #0069FF; color: white; border-color: #0069FF; }
        .admin-btn.ddos.active { background: #E53E3E; border-color: #E53E3E; }
        .status-dot { height: 8px; width: 8px; border-radius: 50%; background: #CBD5E0; }
        .active .status-dot { background: #48BB78; box-shadow: 0 0 0 2px rgba(255,255,255,0.4); }
        
        .footer { background: white; padding: 40px 20px; text-align: center; color: #718096; font-size: 0.9em; margin-top: 60px; border-top: 1px solid #E5E8ED; }
        .footer a { color: #0069FF; text-decoration: none; font-weight: 500 }
    </style>
</head>
<body>
    <div class="header">
        <div class="nav">
            <div class="logo">Bisney</div>
            <div class="nav-links">
                <a href="#">Shop</a>
                <a href="#">Rentals</a>
                
                <div class="nav-icon">
                    ❤️ <span class="badge" id="fav-count">0</span>
                </div>
                <div class="nav-icon">
                    🛒 <span class="badge" id="cart-count">0</span>
                </div>
                
                <a href="/metrics">Metrics</a>
            </div>
        </div>
    </div>
    <div class="hero">
        <h1>Premium Ocean Essentials</h1>
        <p>Build the perfect sandcastle and relax in style</p>
    </div>
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
    
    <div id="toast" class="toast">
        <div style="font-weight:600; margin-bottom:4px" id="toastTitle"></div>
        <div style="font-size:0.9em; color:#718096" id="toastMessage"></div>
    </div>

    <div class="admin-controls">
        <button class="admin-btn" id="latencyBtn" onclick="toggleMode('latency')">
            <span>🐢 Latency Mode</span> <div class="status-dot"></div>
        </button>
        <button class="admin-btn ddos" id="ddosBtn" onclick="toggleMode('ddos')">
            <span>🔥 DDoS Mode</span> <div class="status-dot"></div>
        </button>
    </div>

    <div class="footer"><p>System Health: <a href="/metrics">View Metrics</a> | Powered by Bisney</p></div>

    <script>
        // Global Counters
        let cartTotal = 0;
        let favTotal = 0;

        function updateBadge(id, count) {
            const el = document.getElementById(id);
            el.textContent = count;
            if (count > 0) el.classList.add('visible');
            else el.classList.remove('visible');
        }

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
                if (response.ok) {
                    // Update UI Counter
                    cartTotal++;
                    updateBadge('cart-count', cartTotal);
                    showToast('Added to Cart', `${productName} added successfully!`, 'success');
                } else {
                    showToast('Payment Error', 'Payment gateway timeout', 'error');
                }
            } catch (error) { showToast('Error', 'Unable to reach server', 'error'); }
        }

        async function toggleFavorite(productId) {
            const btn = document.getElementById('fav-' + productId);
            const isAdding = !btn.classList.contains('active');
            
            btn.classList.toggle('active');
            
            // Optimistic UI update
            if (isAdding) favTotal++; else favTotal--;
            updateBadge('fav-count', favTotal);

            try {
                await fetch('/favorite', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({product_id: productId})
                });
            } catch (error) { 
                // Revert if failed
                btn.classList.toggle('active');
                if (isAdding) favTotal--; else favTotal++;
                updateBadge('fav-count', favTotal);
            }
        }

        async function toggleMode(mode) {
            try {
                const response = await fetch('/simulation/' + mode, { method: 'POST' });
                const data = await response.json();
                
                const btn = document.getElementById(mode + 'Btn');
                if (data.active) {
                    btn.classList.add('active');
                    showToast('Simulation Enabled', `${mode.toUpperCase()} mode is now ACTIVE`, 'error');
                } else {
                    btn.classList.remove('active');
                    showToast('Simulation Disabled', `${mode.toUpperCase()} mode is now OFF`, 'success');
                }
            } catch (e) { console.error(e); }
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, products=PRODUCTS)

@app.route('/cart', methods=['POST'])
def cart_checkout():
    """Handle cart checkout with latency tracking"""
    
    inject_latency()

    data = request.get_json() or {}
    product_name = data.get('product_name', 'Unknown')
    tenant_id = 'merch'
    
    with bisney_request_duration_seconds.labels(tenant_id=tenant_id, endpoint='/cart').time():
        with tracer.start_as_current_span("checkout_flow") as span:
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("product", product_name)
            
            # Simulate random failure (10% chance)
            if random.random() < 0.1:
                logger.error("Payment failed", extra={"event": "payment_failure", "tenant_id": tenant_id})
                span.set_status(Status(StatusCode.ERROR, "Payment failed"))
                bisney_requests_total.labels(tenant_id=tenant_id, status='error').inc()
                return jsonify({"error": "Payment timeout"}), 500
            else:
                logger.info("Checkout success", extra={"event": "checkout_success", "tenant_id": tenant_id})
                span.set_status(Status(StatusCode.OK))
                bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
                return jsonify({"message": "Success"}), 200

@app.route('/favorite', methods=['POST'])
def favorite_product():
    
    inject_latency()
    
    tenant_id = 'favorites'
    
    with bisney_request_duration_seconds.labels(tenant_id=tenant_id, endpoint='/favorite').time():
        with tracer.start_as_current_span("favorite_toggle") as span:
            span.set_attribute("tenant_id", tenant_id)
            
            # Simulate Cache Hit/Miss
            if random.random() < 0.7:
                logger.info("Cache hit", extra={"event": "cache_hit", "tenant_id": tenant_id})
                bisney_cache_hits.labels(tenant_id=tenant_id, result='hit').inc()
            else:
                logger.warning("Cache miss", extra={"event": "cache_miss", "tenant_id": tenant_id})
                bisney_cache_hits.labels(tenant_id=tenant_id, result='miss').inc()
                time.sleep(0.1)

            bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
            return jsonify({"message": "Favorite toggled"}), 200

# --- SIMULATION CONTROL ENDPOINTS ---

@app.route('/simulation/<mode>', methods=['POST'])
def toggle_simulation(mode):
    key = f"{mode}_mode"
    if key in SIMULATION_CONFIG:
        SIMULATION_CONFIG[key] = not SIMULATION_CONFIG[key]
        logger.warning(f"Simulation toggled", extra={"event": "sim_toggle", "mode": key, "active": SIMULATION_CONFIG[key]})
        return jsonify({"mode": mode, "active": SIMULATION_CONFIG[key]}), 200
    return jsonify({"error": "Invalid mode"}), 400

@app.route('/metrics')
def metrics():
    if SIMULATION_CONFIG["latency_mode"]:
        lag = random.randint(600, 1200) # Disaster lag
    else:
        lag = random.randint(5, 30) # Normal lag
    
    bisney_inventory_lag.labels(tenant_id="merch").set(lag)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    logger.info("Bisney v2.1 Starting...", extra={"event": "startup"})
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)