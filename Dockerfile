FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Install Nuclei
RUN wget -q https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_3.1.0_linux_amd64.zip \
    && unzip nuclei_3.1.0_linux_amd64.zip \
    && mv nuclei /usr/local/bin/ \
    && rm nuclei_3.1.0_linux_amd64.zip

# Install Subfinder
RUN wget -q https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_2.6.3_linux_amd64.zip \
    && unzip subfinder_2.6.3_linux_amd64.zip \
    && mv subfinder /usr/local/bin/ \
    && rm subfinder_2.6.3_linux_amd64.zip

# Install httpx
RUN wget -q https://github.com/projectdiscovery/httpx/releases/latest/download/httpx_1.3.7_linux_amd64.zip \
    && unzip httpx_1.3.7_linux_amd64.zip \
    && mv httpx /usr/local/bin/ \
    && rm httpx_1.3.7_linux_amd64.zip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/nuclei_templates data/documents logs

# Clone nuclei templates
RUN git clone https://github.com/projectdiscovery/nuclei-templates.git data/nuclei_templates

# Set permissions
RUN chmod +x /usr/local/bin/nuclei /usr/local/bin/subfinder /usr/local/bin/httpx

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "main.py"]