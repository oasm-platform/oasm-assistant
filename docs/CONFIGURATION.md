# Configuration Guide

Environment variable configuration for OASM Assistant.

---

## Configuration File

All configuration is done through `.env` file:

```bash
cp .env.example .env
nano .env
```

---

## Database Configuration

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_strong_password_here
POSTGRES_DB=oasm_assistant
POSTGRES_HOST=oasm-assistant-postgresql
POSTGRES_PORT=5432
```

**Security:** Always use a strong password in production!

---

## LLM Configuration

### Choose Provider

```bash
# Options: ollama, vllm, sglang, openai, anthropic, google
LLM_PROVIDER=ollama
```

### Common Settings

```bash
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3
```

### Provider-Specific Configuration

#### Ollama (Local)

```bash
LLM_PROVIDER=ollama
LLM_MODEL_NAME=qwen2.5:7b
LLM_BASE_URL=http://localhost:8005
```

#### vLLM (GPU)

```bash
LLM_PROVIDER=vllm
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
LLM_BASE_URL=http://localhost:8006/v1

# vLLM-specific
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=8192
VLLM_TENSOR_PARALLEL_SIZE=1
```

#### SGLang (GPU)

```bash
LLM_PROVIDER=sglang
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
LLM_BASE_URL=http://localhost:8007/v1

# SGLang-specific
SGLANG_MODEL=Qwen/Qwen2.5-7B-Instruct
SGLANG_MEM_FRACTION=0.9
SGLANG_CONTEXT_LENGTH=8192
SGLANG_TP_SIZE=1
```

#### OpenAI (Cloud)

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key
LLM_MODEL_NAME=gpt-4o-mini
```

#### Anthropic (Cloud)

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-api-key
LLM_MODEL_NAME=claude-3-5-sonnet-20241022
```

#### Google (Cloud)

```bash
LLM_PROVIDER=google
LLM_API_KEY=your-google-api-key
LLM_MODEL_NAME=gemini-2.0-flash-exp
```

---

## Embedding Configuration

### Choose Provider

```bash
# Options: huggingface, ollama, vllm, sglang, openai, google
EMBEDDING_PROVIDER=huggingface
```

### Common Settings

```bash
EMBEDDING_DIMENSIONS=384
EMBEDDING_TOKEN_LIMIT=512
```

### Provider-Specific Configuration

#### HuggingFace (Local)

```bash
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

#### Ollama (Local)

```bash
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:8005
EMBEDDING_DIMENSIONS=768
```

#### vLLM (GPU)

```bash
EMBEDDING_PROVIDER=vllm
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_BASE_URL=http://localhost:8006/v1
EMBEDDING_DIMENSIONS=384
```

#### SGLang (GPU)

```bash
EMBEDDING_PROVIDER=sglang
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_BASE_URL=http://localhost:8007/v1
EMBEDDING_DIMENSIONS=384
```

#### OpenAI (Cloud)

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

#### Google (Cloud)

```bash
EMBEDDING_PROVIDER=google
EMBEDDING_API_KEY=your-google-api-key
EMBEDDING_MODEL_NAME=models/embedding-001
EMBEDDING_DIMENSIONS=768
```

---

## Application Configuration

```bash
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

---

## Service Configuration

### SearXNG

```bash
SEARXNG_URL=http://oasm-assistant-searxng:8080
SEARXNG_SECRET=your_random_secret_key_here
SEARXNG_BASE_URL=https://localhost:8080/
```

### MCP Integration

```bash
OASM_CORE_API_URL=http://localhost:6276
OASM_CLOUD_APIKEY=change_me
```

### Nuclei Templates

```bash
NUCLEI_TEMPLATES_SYNC_TIME=02:00
NUCLEI_TEMPLATES_REPO_URL=https://github.com/projectdiscovery/nuclei-templates.git
NUCLEI_TEMPLATES_CLONE_DIR=/app/nuclei-templates
```

### Domain Classifier

```bash
DOMAIN_CLASSIFIER_MIN_LABELS=3
DOMAIN_CLASSIFIER_MAX_LABELS=5
DOMAIN_CLASSIFIER_MAX_RETRIES=3
```

---

## Configuration Examples

### Development Setup

```bash
# Database
POSTGRES_PASSWORD=postgres

# LLM - Ollama (easy setup)
LLM_PROVIDER=ollama
LLM_MODEL_NAME=qwen2.5:7b
LLM_BASE_URL=http://localhost:8005

# Embeddings - HuggingFace (local, free)
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# Application
LOG_LEVEL=DEBUG
```

### Production Setup (Local GPU)

```bash
# Database
POSTGRES_PASSWORD=strong_random_password_123

# LLM - SGLang (best for structured output)
LLM_PROVIDER=sglang
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
LLM_BASE_URL=http://localhost:8007/v1
SGLANG_MEM_FRACTION=0.9

# Embeddings - SGLang (fast)
EMBEDDING_PROVIDER=sglang
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_BASE_URL=http://localhost:8007/v1

# Application
LOG_LEVEL=INFO
```

### Production Setup (Cloud)

```bash
# Database
POSTGRES_PASSWORD=strong_random_password_123

# LLM - OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key
LLM_MODEL_NAME=gpt-4o-mini

# Embeddings - OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_MODEL_NAME=text-embedding-3-small

# Application
LOG_LEVEL=INFO
```

---

## Validation

### Check Configuration

```bash
# Validate docker-compose with current .env
docker compose config

# Check environment variables are loaded
docker compose exec oasm-assistant-app env | grep LLM
```

### Test Connections

```bash
# Test database
docker compose exec oasm-assistant-postgresql pg_isready -U postgres

# Test LLM services
curl http://localhost:8005/api/tags  # Ollama
curl http://localhost:8006/health    # vLLM
curl http://localhost:8007/health    # SGLang
```

---

## Troubleshooting

### Configuration Not Loading

```bash
# Ensure .env file exists
ls -la .env

# Check for syntax errors
cat .env

# Restart services to reload configuration
docker compose restart
```

### LLM Connection Failed

```bash
# Verify LLM_BASE_URL is correct
cat .env | grep LLM_BASE_URL

# Check service is running
docker compose ps

# View service logs
docker compose logs oasm-assistant-ollama
```

### Database Connection Failed

```bash
# Verify database credentials
cat .env | grep POSTGRES

# Check database is running
docker compose ps oasm-assistant-postgresql

# View database logs
docker compose logs oasm-assistant-postgresql
```

---

## Security Best Practices

1. **Never commit `.env` to git** - Already in `.gitignore`
2. **Use strong passwords** - Minimum 16 characters
3. **Rotate API keys regularly** - Every 90 days
4. **Use environment-specific configs** - Separate dev/staging/prod
5. **Limit API key permissions** - Minimum required access
6. **Monitor API usage** - Detect anomalies

---

## Next Steps

- **Setup LLM providers** → [LLM Deployment Guide](LLM_DEPLOYMENT.md)
- **Learn about providers** → See comparison tables in LLM guide

---

**Built by Team OASM-Platform**
