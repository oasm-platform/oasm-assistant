# LLM Deployment Guide

## Overview

OASM Assistant supports multiple LLM providers through a unified configuration. This guide covers deploying Ollama with Llama3 8B for local inference.

## System Requirements

**Minimum:** 8GB RAM, 10GB disk, 4 CPU cores
**Recommended:** 16GB+ RAM, 20GB+ SSD, NVIDIA GPU with CUDA

## Quick Start

### 1. Start Ollama

```bash
docker compose up -d ollama
```

### 2. Pull Llama3 8B Model

```bash
docker exec oasm-assistant-ollama ollama pull llama3
```

### 3. Configure Environment

Add to `.env`:

```bash
# LLM Configuration
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434
LLM_MODEL_NAME=llama3
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3
```

### 4. Test Connection

```bash
# Check Ollama API
curl http://localhost:11434/api/tags

# Test model
docker exec oasm-assistant-ollama ollama run llama3 "What is OWASP Top 10?"
```

## Configuration Reference

The application uses `common/config/configs.py` with the following LLM settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | - | Provider name (ollama, openai, anthropic, etc.) |
| `LLM_BASE_URL` | - | API endpoint URL |
| `LLM_MODEL_NAME` | - | Model identifier |
| `LLM_TEMPERATURE` | 0.1 | Randomness (0.0-1.0) |
| `LLM_MAX_TOKENS` | 4000 | Max response length |
| `LLM_TIMEOUT` | 60 | Request timeout (seconds) |
| `LLM_MAX_RETRIES` | 3 | Retry attempts on failure |
| `LLM_API_KEY` | - | API key (if required) |

## Available Models

| Model | Size | RAM | Use Case |
|-------|------|-----|----------|
| llama3 | 4.7GB | 8GB | General security analysis |
| mistral | 4.1GB | 8GB | Fast inference |
| codellama | 3.8GB | 8GB | Code analysis |
| phi3 | 2.3GB | 4GB | Lightweight tasks |

```bash
# Pull additional models
docker exec oasm-assistant-ollama ollama pull mistral
docker exec oasm-assistant-ollama ollama pull codellama
```

## Using Other LLM Providers

### OpenAI

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL_NAME=gpt-4
LLM_TEMPERATURE=0.7
```

### Anthropic Claude

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL_NAME=claude-3-opus-20240229
LLM_TEMPERATURE=0.7
```

### Azure OpenAI

```bash
LLM_PROVIDER=azure
LLM_BASE_URL=https://your-resource.openai.azure.com
LLM_API_KEY=...
LLM_MODEL_NAME=gpt-4
```

## Monitoring

```bash
# Check container status
docker ps | grep ollama

# View logs
docker logs oasm-assistant-ollama

# Resource usage
docker stats oasm-assistant-ollama

# List downloaded models
docker exec oasm-assistant-ollama ollama list
```

## Troubleshooting

### Container Won't Start (GPU Error)

Remove GPU requirements from `docker-compose.yml`:

```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama-data:/root/.ollama
  # Remove deploy.resources section
```

### Out of Memory

Use a smaller model:
```bash
docker exec oasm-assistant-ollama ollama pull phi3
```

Update `.env`:
```bash
LLM_MODEL_NAME=phi3
```

### Model Not Found

```bash
# List available models
docker exec oasm-assistant-ollama ollama list

# Pull missing model
docker exec oasm-assistant-ollama ollama pull llama3
```

### Connection Refused

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart if needed
docker compose restart ollama
```

## Best Practices

1. **Model Selection**: Use `llama3` for balanced performance, `phi3` for resource-constrained environments
2. **Temperature**: Set 0.1-0.3 for factual security analysis, 0.7-0.9 for creative tasks
3. **Monitoring**: Regularly check resource usage with `docker stats`
4. **Backups**: Volume `ollama-data` persists downloaded models
5. **Updates**: Pull latest models periodically for improvements

## References

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama Models Library](https://ollama.com/library)
- [LangChain Ollama Integration](https://python.langchain.com/docs/integrations/llms/ollama)
