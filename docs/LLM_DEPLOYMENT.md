# LLM Deployment Guide

Complete guide for LLM and embedding providers.

---

## Supported Providers

### LLM Providers

| Provider      | Type  | Port | GPU Required | Cost |
| ------------- | ----- | ---- | ------------ | ---- |
| **Ollama**    | Local | 8005 | Optional     | Free |
| **vLLM**      | Local | 8006 | Yes          | Free |
| **SGLang**    | Local | 8007 | Yes          | Free |
| **OpenAI**    | Cloud | -    | No           | Paid |
| **Anthropic** | Cloud | -    | No           | Paid |
| **Google**    | Cloud | -    | No           | Paid |

### Embedding Providers

| Provider        | Type  | Dimensions | Cost |
| --------------- | ----- | ---------- | ---- |
| **HuggingFace** | Local | 384-1024   | Free |
| **Ollama**      | Local | 384-1024   | Free |
| **vLLM**        | Local | 384-1024   | Free |
| **SGLang**      | Local | 384-1024   | Free |
| **OpenAI**      | Cloud | 1536-3072  | Paid |
| **Google**      | Cloud | 768        | Paid |

---

## Quick Start

### 1. Start Services

```bash
# Start all LLM services
docker compose up -d

# Or start specific service
docker compose up oasm-assistant-ollama -d
docker compose up oasm-assistant-vllm -d
docker compose up oasm-assistant-sglang -d
```

### 2. Configure Provider

Edit `.env`:

```bash
# Choose LLM provider
LLM_PROVIDER=ollama  # or vllm, sglang, openai, anthropic, google

# Choose embedding provider
EMBEDDING_PROVIDER=huggingface  # or ollama, vllm, sglang, openai, google
```

### 3. Test Connection

```bash
# Ollama
curl http://localhost:8005/api/tags

# vLLM
curl http://localhost:8006/health

# SGLang
curl http://localhost:8007/health
```

---

## Local Providers

### Ollama

**Best for:** Development, testing, easy setup, CPU/GPU support

#### Features

- ✅ Easy model management
- ✅ CPU and GPU support
- ✅ GGUF quantized models (memory efficient)
- ✅ No API key required
- ✅ Built-in model pulling

#### Setup

```bash
# Start service
docker compose up oasm-assistant-ollama -d

# Pull LLM model
docker compose exec oasm-assistant-ollama ollama pull qwen2.5:7b

# Pull embedding model
docker compose exec oasm-assistant-ollama ollama pull nomic-embed-text

# List models
docker compose exec oasm-assistant-ollama ollama list
```

#### Configuration

```bash
# LLM
LLM_PROVIDER=ollama
LLM_MODEL_NAME=qwen2.5:7b
LLM_BASE_URL=http://localhost:8005

# Embeddings
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:8005
EMBEDDING_DIMENSIONS=768
```

#### Popular Models

**LLM Models:**

| Model        | Size  | RAM | Best For                      |
| ------------ | ----- | --- | ----------------------------- |
| qwen2.5:7b   | 4.7GB | 8GB | General purpose, multilingual |
| llama3:8b    | 4.7GB | 8GB | Chat, reasoning               |
| mistral:7b   | 4.1GB | 8GB | Fast inference                |
| codellama:7b | 3.8GB | 8GB | Code generation               |
| gemma:7b     | 5.0GB | 8GB | Google's model                |

**Embedding Models:**

| Model                  | Dimensions | Size  | Best For          |
| ---------------------- | ---------- | ----- | ----------------- |
| nomic-embed-text       | 768        | 274MB | General purpose   |
| mxbai-embed-large      | 1024       | 669MB | High quality      |
| all-minilm             | 384        | 46MB  | Fast, lightweight |
| snowflake-arctic-embed | 1024       | 669MB | Long documents    |

---

### vLLM

**Best for:** Production, maximum throughput, high performance

#### Features

- ✅ Highest throughput (PagedAttention)
- ✅ Continuous batching
- ✅ OpenAI-compatible API
- ✅ Multi-GPU support (tensor parallelism)
- ✅ HuggingFace model support

#### Setup

```bash
# Start service (model downloads automatically)
docker compose up oasm-assistant-vllm -d

# Monitor download progress
docker compose logs -f oasm-assistant-vllm

# Check health
curl http://localhost:8006/health
```

#### Configuration

```bash
# In .env
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=8192
VLLM_TENSOR_PARALLEL_SIZE=1

# LLM
LLM_PROVIDER=vllm
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
LLM_BASE_URL=http://localhost:8006/v1

# Embeddings
EMBEDDING_PROVIDER=vllm
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_BASE_URL=http://localhost:8006/v1
EMBEDDING_DIMENSIONS=384
```

#### GPU Memory Guidelines

| GPU Model   | VRAM | Memory Setting | Max Model Size |
| ----------- | ---- | -------------- | -------------- |
| RTX 3060    | 12GB | 0.85           | 7B             |
| RTX 3080    | 10GB | 0.80           | 7B             |
| RTX 3090    | 24GB | 0.90           | 13B            |
| RTX 4070 Ti | 12GB | 0.85           | 7B             |
| RTX 4080    | 16GB | 0.90           | 13B            |
| RTX 4090    | 24GB | 0.90           | 13B            |
| A100 40GB   | 40GB | 0.90           | 30B            |
| A100 80GB   | 80GB | 0.90           | 70B            |

#### Popular Models

**LLM Models:**

| Model                                    | Parameters | VRAM | Best For                      |
| ---------------------------------------- | ---------- | ---- | ----------------------------- |
| Qwen/Qwen2.5-7B-Instruct                 | 7B         | 10GB | General purpose, multilingual |
| meta-llama/Llama-2-7b-chat-hf            | 7B         | 10GB | Chat                          |
| mistralai/Mistral-7B-Instruct-v0.2       | 7B         | 10GB | Fast inference                |
| meta-llama/Meta-Llama-3-8B-Instruct      | 8B         | 12GB | Latest Llama                  |
| deepseek-ai/deepseek-coder-6.7b-instruct | 6.7B       | 10GB | Code generation               |

**Embedding Models:**

| Model                  | Dimensions | VRAM | Best For      |
| ---------------------- | ---------- | ---- | ------------- |
| BAAI/bge-small-en-v1.5 | 384        | 2GB  | Fast, general |
| BAAI/bge-base-en-v1.5  | 768        | 3GB  | Balanced      |
| BAAI/bge-large-en-v1.5 | 1024       | 4GB  | Best quality  |

---

### SGLang

**Best for:** Structured output, JSON generation, complex prompts

#### Features

- ✅ 5x faster for JSON generation
- ✅ Structured output (JSON schema, regex)
- ✅ RadixAttention (efficient caching)
- ✅ OpenAI-compatible API
- ✅ Multi-modal support

#### Setup

```bash
# Start service
docker compose up oasm-assistant-sglang -d

# Monitor startup
docker compose logs -f oasm-assistant-sglang

# Check health
curl http://localhost:8007/health
```

#### Configuration

```bash
# In .env
SGLANG_MODEL=Qwen/Qwen2.5-7B-Instruct
SGLANG_MEM_FRACTION=0.9
SGLANG_CONTEXT_LENGTH=8192
SGLANG_TP_SIZE=1

# LLM
LLM_PROVIDER=sglang
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
LLM_BASE_URL=http://localhost:8007/v1

# Embeddings
EMBEDDING_PROVIDER=sglang
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
EMBEDDING_BASE_URL=http://localhost:8007/v1
EMBEDDING_DIMENSIONS=384
```

#### When to Use

**✅ Use SGLang for:**

- JSON generation with schema constraints
- Regex-constrained output
- Many similar prompts (benefits from caching)
- Guided generation
- Structured data extraction

**✅ Use vLLM for:**

- Maximum raw throughput
- Diverse, unrelated prompts
- Most stable and mature solution

#### Performance Benchmarks

| Workload        | SGLang     | vLLM       | Speedup  |
| --------------- | ---------- | ---------- | -------- |
| JSON Generation | 2500 tok/s | 500 tok/s  | **5.0x** |
| Simple Chat     | 1800 tok/s | 1600 tok/s | 1.1x     |
| Multi-turn Chat | 2200 tok/s | 800 tok/s  | **2.7x** |
| Code Generation | 1900 tok/s | 1400 tok/s | 1.4x     |

---

## Cloud Providers

### OpenAI

**Best for:** Quick start, no infrastructure, latest models

#### Configuration

```bash
# LLM
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key
LLM_MODEL_NAME=gpt-4o-mini
LLM_TEMPERATURE=0.1

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

#### Popular Models

**LLM Models:**

- `gpt-4o` - Most capable, expensive
- `gpt-4o-mini` - Fast, cost-effective
- `gpt-4-turbo` - Previous generation
- `gpt-3.5-turbo` - Cheapest, fast

**Embedding Models:**

- `text-embedding-3-small` - 1536 dim, fast
- `text-embedding-3-large` - 3072 dim, best quality
- `text-embedding-ada-002` - 1536 dim, previous gen

---

### Anthropic (Claude)

**Best for:** Long context, reasoning, safety

#### Configuration

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-api-key
LLM_MODEL_NAME=claude-3-5-sonnet-20241022
LLM_TEMPERATURE=0.1
```

#### Popular Models

- `claude-3-5-sonnet-20241022` - Best balance
- `claude-3-opus-20240229` - Most capable
- `claude-3-haiku-20240307` - Fastest, cheapest

**Note:** Anthropic doesn't provide embedding models.

---

### Google (Gemini)

**Best for:** Multimodal, free tier, Google integration

#### Configuration

```bash
# LLM
LLM_PROVIDER=google
LLM_API_KEY=your-google-api-key
LLM_MODEL_NAME=gemini-2.0-flash-exp
LLM_TEMPERATURE=0.1

# Embeddings
EMBEDDING_PROVIDER=google
EMBEDDING_API_KEY=your-google-api-key
EMBEDDING_MODEL_NAME=models/embedding-001
EMBEDDING_DIMENSIONS=768
```

#### Popular Models

**LLM Models:**

- `gemini-2.0-flash-exp` - Latest, experimental
- `gemini-1.5-pro` - Most capable
- `gemini-1.5-flash` - Fast, cost-effective

**Embedding Models:**

- `models/embedding-001` - 768 dim, general purpose

---

## Embedding Providers

### HuggingFace (Default)

**Best for:** Local deployment, no API costs, customization

#### Configuration

```bash
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

#### Popular Models

| Model                                   | Dimensions | Best For       |
| --------------------------------------- | ---------- | -------------- |
| sentence-transformers/all-MiniLM-L6-v2  | 384        | Fast, general  |
| sentence-transformers/all-mpnet-base-v2 | 768        | Better quality |
| BAAI/bge-small-en-v1.5                  | 384        | Good quality   |
| BAAI/bge-base-en-v1.5                   | 768        | Balanced       |
| BAAI/bge-large-en-v1.5                  | 1024       | Best quality   |

---

## Provider Comparison

### Complete Comparison Table

| Feature               | Ollama      | vLLM       | SGLang     | OpenAI      | Anthropic  | Google     |
| --------------------- | ----------- | ---------- | ---------- | ----------- | ---------- | ---------- |
| **Speed**             | ⭐⭐⭐⭐    | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐  | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ |
| **Structured Output** | ⭐⭐        | ⭐⭐⭐     | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐    | ⭐⭐⭐     | ⭐⭐⭐     |
| **Caching**           | ⭐⭐⭐      | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐      | ⭐⭐⭐     | ⭐⭐⭐     |
| **Setup Complexity**  | ⭐⭐⭐⭐⭐  | ⭐⭐⭐     | ⭐⭐⭐     | ⭐⭐⭐⭐⭐  | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Cost**              | Free        | Free       | Free       | Paid        | Paid       | Free tier  |
| **Privacy**           | Local       | Local      | Local      | Cloud       | Cloud      | Cloud      |
| **GPU Required**      | Optional    | Yes        | Yes        | No          | No         | No         |
| **Model Selection**   | Good        | Excellent  | Excellent  | Limited     | Limited    | Limited    |
| **Context Length**    | Up to 128K  | Up to 128K | Up to 128K | Up to 128K  | Up to 200K | Up to 2M   |
| **Embeddings**        | ✅ Yes      | ✅ Yes     | ✅ Yes     | ✅ Yes      | ❌ No      | ✅ Yes     |
| **Best For**          | Development | Production | Structured | Quick start | Reasoning  | Multimodal |

### Detailed Comparison

#### Performance

| Provider  | Throughput    | Latency      | Batch Processing |
| --------- | ------------- | ------------ | ---------------- |
| Ollama    | Medium        | Medium       | Good             |
| vLLM      | **Very High** | Low          | **Excellent**    |
| SGLang    | **Very High** | **Very Low** | **Excellent**    |
| OpenAI    | Very High     | Low          | Good             |
| Anthropic | High          | Medium       | Good             |
| Google    | Very High     | Low          | Good             |

#### Cost (per 1M tokens)

| Provider                      | Input  | Output | Embeddings        |
| ----------------------------- | ------ | ------ | ----------------- |
| Ollama                        | $0     | $0     | $0                |
| vLLM                          | $0     | $0     | $0                |
| SGLang                        | $0     | $0     | $0                |
| OpenAI (GPT-4o-mini)          | $0.15  | $0.60  | $0.02             |
| Anthropic (Claude 3.5 Sonnet) | $3.00  | $15.00 | N/A               |
| Google (Gemini 1.5 Flash)     | $0.075 | $0.30  | $0.00 (free tier) |

#### Resource Requirements

| Provider  | CPU      | RAM     | GPU                   | Disk    |
| --------- | -------- | ------- | --------------------- | ------- |
| Ollama    | 4+ cores | 8GB+    | Optional              | 10GB+   |
| vLLM      | 8+ cores | 16GB+   | Required (10GB+ VRAM) | 20GB+   |
| SGLang    | 8+ cores | 16GB+   | Required (10GB+ VRAM) | 20GB+   |
| OpenAI    | Minimal  | Minimal | No                    | Minimal |
| Anthropic | Minimal  | Minimal | No                    | Minimal |
| Google    | Minimal  | Minimal | No                    | Minimal |

---

## Recommended Setups

### Development

```bash
LLM_PROVIDER=ollama
LLM_MODEL_NAME=qwen2.5:7b
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

**Why:** Easy setup, no GPU required, free

### Production (Single GPU)

```bash
LLM_PROVIDER=sglang
LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
EMBEDDING_PROVIDER=sglang
EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
```

**Why:** Best performance, structured output support

### Production (Multi-GPU)

```bash
LLM_PROVIDER=vllm
VLLM_TENSOR_PARALLEL_SIZE=2
EMBEDDING_PROVIDER=vllm
```

**Why:** Maximum throughput, scalable

### Hybrid (Optimal)

```bash
LLM_PROVIDER=sglang
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=nomic-embed-text
```

**Why:** Best LLM performance, save VRAM for embeddings

### Cloud (No Infrastructure)

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
EMBEDDING_PROVIDER=openai
```

**Why:** No setup, always available, latest models

---

## Performance Tuning

### GPU Memory Optimization

```bash
# Reduce memory usage
VLLM_GPU_MEMORY_UTILIZATION=0.7
SGLANG_MEM_FRACTION=0.7

# Reduce context length
VLLM_MAX_MODEL_LEN=4096
SGLANG_CONTEXT_LENGTH=4096

# Use smaller model
VLLM_MODEL=Qwen/Qwen2.5-1.5B-Instruct
```

### Multi-GPU Setup

```bash
# vLLM
VLLM_TENSOR_PARALLEL_SIZE=2  # For 2 GPUs
VLLM_TENSOR_PARALLEL_SIZE=4  # For 4 GPUs

# SGLang
SGLANG_TP_SIZE=2  # For 2 GPUs
```

---

## Troubleshooting

### Connection Issues

```bash
# Check service status
docker compose ps

# View logs
docker compose logs oasm-assistant-ollama
docker compose logs oasm-assistant-vllm
docker compose logs oasm-assistant-sglang

# Restart service
docker compose restart oasm-assistant-vllm
```

### GPU Issues

```bash
# Check GPU
nvidia-smi

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Restart Docker
sudo systemctl restart docker
```

### Model Issues

```bash
# Ollama: Pull model
docker compose exec oasm-assistant-ollama ollama pull qwen2.5:7b

# vLLM/SGLang: Check download progress
docker compose logs -f oasm-assistant-vllm

# Check disk space
df -h
```

---

## Health Checks

```bash
# Ollama
curl http://localhost:8005/api/tags

# vLLM
curl http://localhost:8006/health
curl http://localhost:8006/v1/models

# SGLang
curl http://localhost:8007/health
curl http://localhost:8007/v1/models
curl http://localhost:8007/get_server_info
```

---

**Built by Team OASM-Platform**
