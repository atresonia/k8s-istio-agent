# Kubernetes & Istio AI Troubleshooting Agent

A clean, enterprise-ready AI agent for troubleshooting Kubernetes and Istio issues. Designed to be LLM-agnostic and work with your internal infrastructure.

## Documentation

- **[Contributing Guide](CONTRIBUTING.md)** – How to contribute to the project
- **[Changelog](CHANGELOG.md)** – Version history and release notes
- **[Local Setup & Examples](local_setup/)** – Example configs and scripts for running with HuggingFace and other LLMs locally

## Quick Start

### 1. Installation

```bash
git clone <repository>
cd k8s-istio-agent
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Check system requirements for HuggingFace
python huggingface_example.py --check

# Create configuration
cp config.yaml.example config.yaml
# Edit config.yaml with your LLM provider settings
```

### 3. Run Locally

```bash
# Interactive CLI
python main.py interactive

# Single query
python main.py query "My pods are not starting"

# Web interface
python main.py web
```

## Architecture

```
┌─────────────────────────────────────────┐
│              User Interface             │
│    (CLI, Web UI, API, Slack Bot)        │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│           Agent Controller              │
│   (Task routing, context management)    │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼──────────────────────────┐
│          LLM Abstraction Layer         │
│     (Provider-agnostic interface)      │
└───┬─────────┬─────────┬─────────┬──────┘
    │         │         │         │
┌───▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼──────┐
│OpenAI │ │Hugging │ │Azure │ │ Internal │
│ API   │ │ Face   │ │OpenAI│ │ Wrappers │
└───────┘ └────────┘ └──────┘ └──────────┘

┌─────────────────────────────────────────┐
│            Tool Registry                │
│    (Kubernetes, Istio, Observability)   │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│          Execution Engine               │
│    (Safe command execution, context)    │
└─────────────────────────────────────────┘
```

## LLM Provider Support

### HuggingFace (Local Models)
```yaml
llm:
  provider: "huggingface"
  config:
    model_name: "microsoft/DialoGPT-medium"
    device: "auto"
    load_in_8bit: true  # Memory optimization
    max_length: 1024
    temperature: 0.7
```

### OpenAI
```yaml
llm:
  provider: "openai"
  config:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4"
```

### Azure OpenAI
```yaml
llm:
  provider: "azure"
  config:
    azure_endpoint: "https://your-resource.openai.azure.com/"
    api_key: "${AZURE_OPENAI_API_KEY}"
    api_version: "2023-12-01-preview"
    deployment_name: "gpt-4"
```

### Internal/Enterprise
```yaml
llm:
  provider: "internal"
  config:
    endpoint: "https://internal-llm.company.com"
    api_key: "${INTERNAL_API_KEY}"
    model: "company-gpt-4"
```

## 🛠️ Available Tools

### Kubernetes Tools
- **kubectl**: Safe kubectl commands (get, describe, logs, etc.)
- **logs**: Advanced log analysis with pattern matching
- **resources**: Resource usage and health monitoring

### Istio Tools
- **istio_proxy**: Proxy status and configuration analysis
- **istio_config**: Configuration validation and analysis
- **traffic**: Traffic flow and routing analysis

### Observability Tools (placeholder, not yet implemented)
- **prometheus**: Metrics querying and analysis
- **grafana**: Dashboard integration (coming soon)

## 📋 Use Cases

### Pod Troubleshooting
```
🤖 What can I help you troubleshoot? 
My frontend pods are not starting

🔍 I'll investigate the pod startup issues. Let me check the current status:

kubectl get pods -n frontend

✅ Found pods in ImagePullBackOff status. Let me get more details:

kubectl describe pod frontend-deployment-abc123 -n frontend

🔍 Root cause: Image pull authentication failure
💡 Solution: Configure imagePullSecrets for private registry access
```

### Service Mesh Issues
```
🤖 What can I help you troubleshoot?
Traffic between services is failing intermittently

🔍 Let me check your Istio service mesh configuration:

istio_proxy status

✅ Found stale EDS configuration on backend service
🔍 Checking traffic patterns:

prometheus query 'istio_request_total{destination_service_name="backend"}'

💡 Recommendation: Restart affected pods to refresh Envoy configuration
```

## Deployment Options

### Option 1: Local Development
```bash
python main.py interactive --config config_dev.yaml
```

### Option 2: In-Cluster Deployment
```bash
# Build and deploy
docker build -t k8s-istio-agent:latest .
kubectl apply -f k8s/
```

### Option 3: Azure Container Instance
```bash
az container create \
  --resource-group myResourceGroup \
  --name k8s-agent \
  --image k8s-istio-agent:latest \
  --environment-variables LLM_API_KEY=$API_KEY
```

## Security Features

- **RBAC**: Minimal required permissions
- **Read-only Operations**: No destructive commands
- **Safe Command Filtering**: Whitelist of allowed operations
- **Secret Management**: Secure credential handling
- **Non-root Container**: Security-hardened deployment

## 📊 Example Troubleshooting Workflow

```python
# 1. User reports issue
user_query = "My application has high latency"

# 2. Agent investigates systematically
agent.process_query(user_query)
# - Checks pod status and resource usage
# - Analyzes application logs for errors
# - Reviews Istio metrics for service mesh issues
# - Examines Prometheus metrics for performance bottlenecks

# 3. Provides actionable recommendations
# - Identifies resource constraints
# - Suggests configuration optimizations
# - Recommends scaling strategies
```

## Key Advantages

### vs. kagent
- ✅ **No Autogen Dependency**: Clean, purpose-built architecture
- ✅ **Enterprise Ready**: Works with internal LLM wrappers
- ✅ **LLM Flexibility**: Easy provider swapping
- ✅ **Focused Scope**: Kubernetes/Istio specific
- ✅ **Simple Codebase**: Easy to understand and extend

### vs. Manual Troubleshooting
- ✅ **Systematic Approach**: Follows best practice workflows
- ✅ **Knowledge Retention**: Learns from patterns
- ✅ **Faster Resolution**: Automated investigation steps
- ✅ **Comprehensive Analysis**: Multi-tool correlation

## 📁 Project Structure

```
k8s-istio-agent/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── config.yaml            # Configuration
├── Dockerfile             # Container build
├── llm/                   # LLM providers
│   ├── provider.py        # Base abstractions
│   └── providers/         # Specific implementations
├── tools/                 # Tool system
│   ├── base.py           # Tool abstractions
│   ├── registry.py       # Tool management
│   ├── kubernetes/       # K8s tools
│   ├── istio/           # Istio tools
│   └── observability/   # Monitoring tools
├── agent/               # Agent logic
│   └── controller.py    # Main orchestration
├── web/                # Web interface
│   ├── app.py         # FastAPI application
│   └── templates/     # HTML templates
└── k8s/               # Kubernetes manifests
│   ├── deployment.yaml         # FastAPI application
│   ├── service.yaml     # HTML templates
│   └── rbac.yaml     # HTML templates
└── tests/               # Test suite
    ├── __init__.py     # Test package
    ├── conftest.py     # Test configuration
    ├── unit/           # Unit tests
    │   ├── test_llm.py        # LLM provider tests
    │   ├── test_tools.py      # Tool tests
    │   └── test_agent.py      # Agent logic tests
    ├── integration/    # Integration tests
    │   ├── test_k8s.py        # Kubernetes integration
    │   ├── test_istio.py      # Istio integration
    │   └── test_web.py        # Web interface tests
    └── e2e/           # End-to-end tests
        ├── test_flows.py      # Common workflows
        └── test_scenarios.py  # Real-world scenarios



```

## Configuration Examples

### Lightweight (CPU-only)
```yaml
llm:
  provider: "huggingface"
  config:
    model_name: "microsoft/DialoGPT-small"
    device: "cpu"
    torch_dtype: "float32"
```

### Production (Quantized)
```yaml
llm:
  provider: "huggingface"
  config:
    model_name: "microsoft/DialoGPT-medium"
    device: "auto"
    load_in_8bit: true
```

### Enterprise (Internal)
```yaml
llm:
  provider: "internal"
  config:
    endpoint: "https://langchain-api.company.com"
    api_key: "${COMPANY_LLM_KEY}"
```

## Azure POC Setup

### 1. Create AKS Cluster
```bash
az aks create \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys
```

### 2. Install Istio
```bash
istioctl install --set values.defaultRevision=default
kubectl label namespace default istio-injection=enabled
```

### 3. Deploy Agent
```bash
kubectl apply -f k8s/
```

### 4. Access Web Interface
```bash
kubectl port-forward svc/k8s-istio-agent 8080:80 -n troubleshooting
# Open http://localhost:8080
```

## Contributing

1. **Add New Tools**: Extend `tools/` directory
2. **New LLM Providers**: Add to `llm/providers/`
3. **Enhanced Workflows**: Modify `agent/controller.py`
4. **UI Improvements**: Update `web/` components

Create a PR and we will review it.
