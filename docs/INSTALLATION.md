# Installation Guide

Step-by-step installation guide for OASM Assistant.

---

## System Requirements

### Minimum

- **CPU**: 4 cores
- **RAM**: 8GB
- **Disk**: 50GB free space
- **OS**: Linux (Ubuntu 20.04+, Debian 11+)

### Recommended

- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Disk**: 100GB+ SSD
- **GPU**: NVIDIA GPU with 10GB+ VRAM (for local LLM)
- **OS**: Ubuntu 22.04 LTS

---

## Prerequisites

### Required Software

- Docker 20.10+
- Docker Compose 2.0+
- Git

### Optional (for GPU support)

- NVIDIA GPU drivers
- NVIDIA Container Toolkit

---

## Installation Steps

### 1. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### 2. Install NVIDIA Docker (Optional - for GPU)

**Skip this if you don't have NVIDIA GPU**

```bash
# Add NVIDIA repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install NVIDIA Container Toolkit
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 3. Clone Repository

```bash
git clone https://github.com/your-org/oasm-assistant.git
cd oasm-assistant
```

### 4. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

**Minimum required changes:**

```bash
# Set strong database password
POSTGRES_PASSWORD=your_strong_password_here

# Choose LLM provider
LLM_PROVIDER=ollama  # or vllm, sglang, openai
```

> See [Configuration Guide](CONFIGURATION.md) for all options.

### 5. Start Services

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check service status
docker compose ps
```

### 6. Initialize LLM (if using Ollama)

```bash
# Pull model
docker compose exec oasm-assistant-ollama ollama pull qwen2.5:7b

# Verify
docker compose exec oasm-assistant-ollama ollama list
```

---

## Verification

### Check Services

```bash
# All services should be "Up" or "healthy"
docker compose ps
```

### Test Database

```bash
docker compose exec oasm-assistant-postgresql pg_isready -U postgres
```

### Test LLM Services

```bash
# Ollama (port 8005)
curl http://localhost:8005/api/tags

# vLLM (port 8006)
curl http://localhost:8006/health

# SGLang (port 8007)
curl http://localhost:8007/health
```

### Check Application Logs

```bash
# View application logs
docker compose logs oasm-assistant-app

# Check for errors
docker compose logs oasm-assistant-app | grep -i error
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Restart Docker daemon
sudo systemctl restart docker
docker compose up -d
```

### Database Connection Failed

```bash
# Check database is running
docker compose ps oasm-assistant-postgresql

# View database logs
docker compose logs oasm-assistant-postgresql

# Verify credentials in .env
cat .env | grep POSTGRES

# Restart database
docker compose restart oasm-assistant-postgresql
```

### GPU Not Detected

```bash
# Check NVIDIA drivers
nvidia-smi

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Restart Docker
sudo systemctl restart docker
docker compose down
docker compose up -d
```

### Out of Memory

```bash
# Check memory usage
free -h
docker stats

# Reduce GPU memory usage (edit .env)
VLLM_GPU_MEMORY_UTILIZATION=0.7
SGLANG_MEM_FRACTION=0.7

# Restart services
docker compose restart
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :8005

# Stop conflicting service or change port in docker-compose.yml
```

### Model Download Failed

```bash
# Check internet connection
ping -c 3 huggingface.co

# Check disk space
df -h

# Retry download
docker compose restart oasm-assistant-vllm

# Manual download (Ollama)
docker compose exec oasm-assistant-ollama ollama pull qwen2.5:7b
```

---

## Post-Installation

### Configure Firewall (if needed)

```bash
# Allow application port
sudo ufw allow 8000/tcp

# Allow LLM ports (if accessing from other machines)
sudo ufw allow 8005/tcp
sudo ufw allow 8006/tcp
sudo ufw allow 8007/tcp
```

### Enable Auto-Start

```bash
# Enable Docker to start on boot
sudo systemctl enable docker

# Services will auto-start with Docker (restart: unless-stopped)
```

---

## Uninstallation

### Stop Services

```bash
docker compose down
```

### Remove Data (Optional)

```bash
# WARNING: This deletes all data!
docker compose down -v

# Remove images
docker compose down --rmi all
```

### Remove Repository

```bash
cd ..
rm -rf oasm-assistant
```

---

## Next Steps

1. **Configure your setup** → [Configuration Guide](CONFIGURATION.md)
2. **Setup LLM providers** → [LLM Deployment Guide](LLM_DEPLOYMENT.md)
3. **Start using the system** → User Guide (coming soon)

---

**Built by Team OASM-Platform**
