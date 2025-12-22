from flask import Flask, request, jsonify, render_template_string
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
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

# Prometheus Metrics
bisney_requests_total = Counter(
    'bisney_requests_total',
    'Total requests by tenant and status',
    ['tenant_id', 'status']
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
coupon_clicks = 0
disaster_mode = False

# HTML UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bisney Simulator</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .button-group {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin: 30px 0;
        }
        button {
            padding: 20px 40px;
            font-size: 1.2em;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .cart-btn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        .coupon-btn {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        .disaster-btn {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            color: #333;
        }
        .disaster-btn.active {
            background: linear-gradient(135deg, #ff0844 0%, #ffb199 100%);
            color: white;
        }
        button:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }
        button:active {
            transform: translateY(-1px);
        }
        .status {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            min-height: 100px;
        }
        .status h3 {
            margin-top: 0;
        }
        .response {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            font-family: monospace;
        }
        .success {
            background: rgba(76, 175, 80, 0.3);
            border-left: 4px solid #4CAF50;
        }
        .error {
            background: rgba(244, 67, 54, 0.3);
            border-left: 4px solid #f44336;
        }
        .info {
            background: rgba(33, 150, 243, 0.3);
            border-left: 4px solid #2196F3;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎢 Bisney Simulator 🎢</h1>
        <div class="button-group">
            <button class="cart-btn" onclick="addToCart()">🛒 Add to Cart (Merch)</button>
            <button class="coupon-btn" onclick="validateCoupon()">🎟️ Validate Coupon</button>
            <button class="disaster-btn" id="disasterBtn" onclick="toggleDisaster()">
                🔥 Disaster Mode: OFF
            </button>
        </div>
        <div class="status">
            <h3>Status:</h3>
            <div id="statusOutput">Ready to simulate...</div>
        </div>
        <div class="footer">
            <p>Metrics available at <a href="/metrics" style="color: #fff; font-weight: bold;">/metrics</a></p>
        </div>
    </div>

    <script>
        async function addToCart() {
            const output = document.getElementById('statusOutput');
            output.innerHTML = '<div class="info">Processing cart checkout...</div>';
            
            try {
                const response = await fetch('/cart', { method: 'POST' });
                const data = await response.json();
                
                if (response.ok) {
                    output.innerHTML = `<div class="success">✅ Cart checkout successful!<br>Click count: ${data.clicks}</div>`;
                } else {
                    output.innerHTML = `<div class="error">❌ Payment failed!<br>${data.error}<br>Click count: ${data.clicks}</div>`;
                }
            } catch (error) {
                output.innerHTML = `<div class="error">❌ Request failed: ${error.message}</div>`;
            }
        }

        async function validateCoupon() {
            const output = document.getElementById('statusOutput');
            output.innerHTML = '<div class="info">Validating coupon...</div>';
            
            try {
                const response = await fetch('/coupon', { method: 'POST' });
                const data = await response.json();
                
                if (response.ok) {
                    output.innerHTML = `<div class="success">✅ Coupon validated!<br>Cache: ${data.cache}<br>Duration: ${data.duration}s</div>`;
                } else {
                    output.innerHTML = `<div class="error">❌ Validation failed</div>`;
                }
            } catch (error) {
                output.innerHTML = `<div class="error">❌ Request failed: ${error.message}</div>`;
            }
        }

        async function toggleDisaster() {
            const output = document.getElementById('statusOutput');
            const btn = document.getElementById('disasterBtn');
            
            try {
                const response = await fetch('/disaster', { method: 'POST' });
                const data = await response.json();
                
                if (data.disaster_mode) {
                    btn.textContent = '🔥 Disaster Mode: ON';
                    btn.classList.add('active');
                    output.innerHTML = '<div class="error">⚠️ Disaster Mode ACTIVATED! Inventory lag increased!</div>';
                } else {
                    btn.textContent = '🔥 Disaster Mode: OFF';
                    btn.classList.remove('active');
                    output.innerHTML = '<div class="success">✅ Disaster Mode deactivated. Systems normal.</div>';
                }
            } catch (error) {
                output.innerHTML = `<div class="error">❌ Request failed: ${error.message}</div>`;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the UI"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/cart', methods=['POST'])
def cart_checkout():
    """Handle cart checkout with tracing and failure simulation"""
    global cart_clicks
    cart_clicks += 1
    
    tenant_id = 'merch'
    
    # Start OpenTelemetry span
    with tracer.start_as_current_span("checkout_flow") as span:
        span.set_attribute("tenant_id", tenant_id)
        span.set_attribute("click_count", cart_clicks)
        
        # Every 3rd click fails
        if cart_clicks % 3 == 0:
            # Failure scenario
            logger.error(
                "Payment processing failed",
                extra={
                    "event": "payment_failure",
                    "tenant_id": tenant_id,
                    "click_count": cart_clicks,
                    "reason": "simulated_failure"
                }
            )
            
            span.set_status(Status(StatusCode.ERROR, "Payment processing failed"))
            bisney_requests_total.labels(tenant_id=tenant_id, status='error').inc()
            
            # Update inventory lag (disaster mode affects this)
            if disaster_mode:
                bisney_inventory_lag.labels(tenant_id=tenant_id).set(600)
            else:
                bisney_inventory_lag.labels(tenant_id=tenant_id).set(120)
            
            return jsonify({
                "error": "Payment gateway timeout",
                "clicks": cart_clicks
            }), 500
        else:
            # Success scenario
            logger.info(
                "Cart checkout successful",
                extra={
                    "event": "checkout_success",
                    "tenant_id": tenant_id,
                    "click_count": cart_clicks
                }
            )
            
            span.set_status(Status(StatusCode.OK))
            bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
            
            # Update inventory lag
            if disaster_mode:
                bisney_inventory_lag.labels(tenant_id=tenant_id).set(600)
            else:
                bisney_inventory_lag.labels(tenant_id=tenant_id).set(15)
            
            return jsonify({
                "message": "Checkout successful",
                "clicks": cart_clicks
            }), 200

@app.route('/coupon', methods=['POST'])
def coupon_validation():
    """Handle coupon validation with tracing and cache simulation"""
    global coupon_clicks
    coupon_clicks += 1
    
    tenant_id = 'coupons'
    
    # Start OpenTelemetry span
    with tracer.start_as_current_span("coupon_validation") as span:
        span.set_attribute("tenant_id", tenant_id)
        span.set_attribute("click_count", coupon_clicks)
        
        # Every 2nd click is a cache miss
        if coupon_clicks % 2 == 0:
            # Cache miss
            logger.warning(
                "Coupon cache miss",
                extra={
                    "event": "cache_miss",
                    "tenant_id": tenant_id,
                    "click_count": coupon_clicks
                }
            )
            
            span.set_attribute("cache_result", "miss")
            bisney_cache_hits.labels(tenant_id=tenant_id, result='miss').inc()
            
            # Simulate slow database lookup
            time.sleep(0.8)
            duration = 0.8
        else:
            # Cache hit
            logger.info(
                "Coupon cache hit",
                extra={
                    "event": "cache_hit",
                    "tenant_id": tenant_id,
                    "click_count": coupon_clicks
                }
            )
            
            span.set_attribute("cache_result", "hit")
            bisney_cache_hits.labels(tenant_id=tenant_id, result='hit').inc()
            
            # Fast cache response
            time.sleep(0.05)
            duration = 0.05
        
        span.set_status(Status(StatusCode.OK))
        bisney_requests_total.labels(tenant_id=tenant_id, status='success').inc()
        
        return jsonify({
            "message": "Coupon validated",
            "cache": "hit" if coupon_clicks % 2 == 1 else "miss",
            "duration": duration
        }), 200

@app.route('/disaster', methods=['POST'])
def toggle_disaster():
    """Toggle disaster mode"""
    global disaster_mode
    disaster_mode = not disaster_mode
    
    logger.info(
        "Disaster mode toggled",
        extra={
            "event": "disaster_mode_toggle",
            "disaster_mode": disaster_mode
        }
    )
    
    return jsonify({
        "disaster_mode": disaster_mode
    }), 200

@app.route('/metrics')
def metrics():
    """Expose Prometheus metrics"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    logger.info(
        "Bisney Simulator starting",
        extra={
            "event": "app_startup",
            "port": 5001
        }
    )
    
    # Initialize metrics with zero values
    for tenant in ['merch', 'coupons']:
        bisney_requests_total.labels(tenant_id=tenant, status='success').inc(0)
        bisney_requests_total.labels(tenant_id=tenant, status='error').inc(0)
        bisney_inventory_lag.labels(tenant_id=tenant).set(0)
        bisney_cache_hits.labels(tenant_id=tenant, result='hit').inc(0)
        bisney_cache_hits.labels(tenant_id=tenant, result='miss').inc(0)
    
    app.run(host='0.0.0.0', port=5001, debug=False)
