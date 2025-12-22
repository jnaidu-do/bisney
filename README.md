# Bisney Simulator

A Flask application that generates rich telemetry (metrics, logs, traces) for observability testing.

## Features

- **Prometheus Metrics**: Exposed at `/metrics`
- **Structured JSON Logs**: Output to stdout
- **OpenTelemetry Traces**: Manual instrumentation for key flows
- **Multi-tenant**: All telemetry tagged with `tenant_id` (merch/coupons)
- **Failure Simulation**: Every 3rd cart click fails

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Visit `http://localhost:5001` for the UI.

## Deploy to DigitalOcean Droplet

### Prerequisites
- A DigitalOcean account
- SSH key configured

### Option 1: Quick Deploy (Recommended)

1. **Create a Droplet**
   - Go to DigitalOcean Console → Create → Droplets
   - Choose: Ubuntu 22.04 LTS
   - Plan: Basic ($6/month - 1GB RAM, 1 vCPU)
   - Add your SSH key
   - Create Droplet

2. **SSH into your droplet**
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```

3. **Install Docker & Docker Compose**
   ```bash
   # Update packages
   apt update && apt upgrade -y
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Install Docker Compose
   apt install docker-compose -y
   
   # Verify installation
   docker --version
   docker-compose --version
   ```

4. **Deploy the Application**
   ```bash
   # Create app directory
   mkdir -p /opt/bisney
   cd /opt/bisney
   
   # Clone or copy your files (choose one method):
   
   # Method A: If using Git
   git clone YOUR_REPO_URL .
   
   # Method B: Manual upload (from your local machine)
   # scp -r /Users/jayanthnaidu/dev/bisney/* root@YOUR_DROPLET_IP:/opt/bisney/
   ```

5. **Start the Application**
   ```bash
   cd /opt/bisney
   docker-compose up -d
   ```

6. **Verify it's running**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

7. **Configure Firewall**
   ```bash
   # Allow SSH, HTTP, and app port
   ufw allow 22/tcp
   ufw allow 5001/tcp
   ufw --force enable
   ```

8. **Access Your App**
   - UI: `http://YOUR_DROPLET_IP:5001`
   - Metrics: `http://YOUR_DROPLET_IP:5001/metrics`

### Option 2: Manual Deploy (Without Docker)

```bash
# SSH into droplet
ssh root@YOUR_DROPLET_IP

# Install Python
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv -y

# Create app directory
mkdir -p /opt/bisney
cd /opt/bisney

# Copy files (from local machine)
# scp -r /Users/jayanthnaidu/dev/bisney/* root@YOUR_DROPLET_IP:/opt/bisney/

# Install dependencies
pip3 install -r requirements.txt

# Run with systemd (persistent)
cat > /etc/systemd/system/bisney.service << 'EOF'
[Unit]
Description=Bisney Simulator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bisney
ExecStart=/usr/bin/python3 /opt/bisney/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable bisney
systemctl start bisney
systemctl status bisney

# Configure firewall
ufw allow 22/tcp
ufw allow 5001/tcp
ufw --force enable
```

### Useful Commands

```bash
# Check logs (Docker)
docker-compose logs -f

# Check logs (systemd)
journalctl -u bisney -f

# Restart app (Docker)
docker-compose restart

# Restart app (systemd)
systemctl restart bisney

# Stop app (Docker)
docker-compose down

# Update app (Docker)
docker-compose down
docker-compose pull
docker-compose up -d

# Check container health
docker ps
curl http://localhost:5001/metrics
```

### Production Considerations

1. **Use a Reverse Proxy (Nginx)**
   ```bash
   apt install nginx -y
   
   cat > /etc/nginx/sites-available/bisney << 'EOF'
   server {
       listen 80;
       server_name YOUR_DOMAIN_OR_IP;
       
       location / {
           proxy_pass http://localhost:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   EOF
   
   ln -s /etc/nginx/sites-available/bisney /etc/nginx/sites-enabled/
   nginx -t
   systemctl restart nginx
   
   # Update firewall
   ufw allow 80/tcp
   ```

2. **Add SSL with Let's Encrypt** (if you have a domain)
   ```bash
   apt install certbot python3-certbot-nginx -y
   certbot --nginx -d yourdomain.com
   ```

3. **Monitor Resource Usage**
   ```bash
   htop
   docker stats
   ```

### Troubleshooting

```bash
# Check if port is listening
netstat -tlnp | grep 5001

# Check Docker logs
docker logs bisney-simulator

# Check system logs
journalctl -xe

# Test app locally on droplet
curl http://localhost:5001
curl http://localhost:5001/metrics

# Rebuild Docker image
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Architecture

```
User Browser → Droplet (Port 5001) → Flask App
                                    ↓
                                Prometheus Metrics (/metrics)
                                JSON Logs (stdout)
                                OpenTelemetry Traces (console)
```

## Telemetry Endpoints

- **UI**: `http://YOUR_IP:5001/`
- **Metrics**: `http://YOUR_IP:5001/metrics`
- **Health**: Check metrics endpoint for 200 response

## Metrics Available

- `bisney_requests_total{tenant_id, status}` - Total requests counter
- `bisney_inventory_lag{tenant_id}` - Inventory sync lag gauge
- `bisney_cache_hits{tenant_id, result}` - Cache hit/miss counter
