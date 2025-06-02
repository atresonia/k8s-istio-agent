# Local Setup Guide - Testing with HuggingFace Models

This guide will help you quickly set up and test the K8s Istio Agent with HuggingFace models on your local machine.

## 🔧 Prerequisites

### System Requirements
- **Python**: 3.9 or higher
- **Memory**: 4GB+ RAM (8GB+ recommended)
- **Storage**: 2GB+ free space for models
- **OS**: Linux, macOS, or Windows with WSL2

### Optional but Recommended
- **kubectl**: For testing Kubernetes integration
- **Docker**: For containerized testing
- **minikube/kind**: For local Kubernetes cluster

## 🚀 Quick Start (5 minutes)

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd k8s-istio-agent

# Create virtual environment
conda create --name istiok8sagent python=3.12
conda activate istiok8sagent

# Install dependencies
pip install -r requirements.txt
```

### 2. Check System Compatibility
```bash
# Check if your system can run HuggingFace models
python huggingface_example.py --check
```

**Expected Output:**
```
🔧 System Requirements Check
==============================
RAM: 8.0 GB
✅ Sufficient RAM for medium/large models
GPU 0: NVIDIA GeForce RTX 3080 (10.0 GB)
✅ CUDA available - can use GPU acceleration

💡 Recommendations:
   • Can use DialoGPT-large
   • Try load_in_4bit for even better performance
```

### 3. Create Configuration
```bash
# Generate optimized config for your system
python huggingface_example.py --config quantized
```

This creates `config_hf_quantized.yaml`:
```yaml
llm:
  provider: "huggingface"
  config:
    model_name: "microsoft/DialoGPT-medium"
    device: "auto"
    load_in_8bit: true
    max_length: 1024
    temperature: 0.7
```

### 4. Test the Agent
```bash
# Start interactive mode
python main.py interactive --config config_hf_quantized.yaml
```

## 📱 Model Selection Guide

### For Low-Resource Systems (2-4GB RAM)
```bash
python huggingface_example.py --config lightweight
```
- **Model**: `microsoft/DialoGPT-small`
- **Memory**: ~2GB
- **Performance**: Good for basic troubleshooting

### For Development/Testing (4-8GB RAM)
```bash
python huggingface_example.py --config quantized
```
- **Model**: `microsoft/DialoGPT-medium`
- **Memory**: ~3GB (with 8-bit quantization)
- **Performance**: Balanced quality/speed

### For High Performance (8GB+ RAM)
```bash
python huggingface_example.py --config large
```
- **Model**: `microsoft/DialoGPT-large`
- **Memory**: ~6GB (with 4-bit quantization)
- **Performance**: Best quality responses

### For Code/Config Analysis
```bash
python huggingface_example.py --config code_focused
```
- **Model**: `microsoft/codebert-base`
- **Memory**: ~3GB
- **Performance**: Optimized for YAML/config analysis

## 🧪 Testing Scenarios

### Scenario 1: Basic Agent Test
```bash
python main.py interactive --config config_hf_quantized.yaml
```

**Test Query:**
```
🤖 What can I help you troubleshoot? 
My pods are not starting
```

**Expected Response:**
```
I'll help you investigate pod startup issues. Let me check the current pod status:

kubectl get pods

✅ kubectl executed successfully:
NAME                           READY   STATUS    RESTARTS   AGE
frontend-deployment-123        0/1     Pending   0          2m
backend-deployment-456         1/1     Running   0          2d

I can see you have a pod in Pending status. Let me get more details...
```

### Scenario 2: Web Interface Test
```bash
# Start web interface
python main.py web --config config_hf_quantized.yaml
```

1. Open http://localhost:8080
2. Try example queries from the web interface
3. Test real-time chat functionality

### Scenario 3: Single Query Test
```bash
# Test single query mode
python main.py query "Check cluster health" --config config_hf_quantized.yaml
```

## 🐛 Troubleshooting

### Issue: Out of Memory
```
RuntimeError: CUDA out of memory
```

**Solutions:**
1. **Enable quantization:**
   ```yaml
   load_in_8bit: true  # or load_in_4bit: true
   ```

2. **Use smaller model:**
   ```yaml
   model_name: "microsoft/DialoGPT-small"
   ```

3. **Force CPU usage:**
   ```yaml
   device: "cpu"
   torch_dtype: "float32"
   ```

### Issue: Slow Loading
```
Model loading taking too long...
```

**Solutions:**
1. **First run**: Models download from HuggingFace (1-2GB)
2. **Subsequent runs**: Models load from cache (~30 seconds)
3. **Speed up**: Use smaller models or enable quantization

### Issue: ImportError
```
ImportError: No module named 'transformers'
```

**Solution:**
```bash
# Reinstall with specific versions
pip install transformers==4.30.0 torch>=2.0.0 accelerate>=0.20.0
```

### Issue: Kubernetes Tools Not Available
```
kubectl not found or not accessible
```

**Solutions:**
1. **Install kubectl:**
   ```bash
   # macOS
   brew install kubectl
   
   # Linux
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   chmod +x kubectl && sudo mv kubectl /usr/local/bin/
   ```

2. **Test without K8s (simulation mode):**
   The agent works with simulated kubectl responses for testing

## 📊 Performance Benchmarks

### Model Loading Times (First Run)
| Model | Size | Download | Load Time | Memory |
|-------|------|----------|-----------|---------|
| DialoGPT-small | ~450MB | 2-3 min | 15s | 2GB |
| DialoGPT-medium | ~850MB | 3-5 min | 30s | 3GB |
| DialoGPT-large | ~1.5GB | 5-8 min | 45s | 6GB |

### Response Times
| Model | Query Type | Avg Response | Quality |
|-------|------------|--------------|---------|
| Small | Simple | 2-5s | Good |
| Medium | Complex | 5-10s | Very Good |
| Large | Complex | 8-15s | Excellent |

## 🔄 Development Workflow

### 1. Start Development
```bash
# Activate environment
source venv/bin/activate

# Start with lightweight model for development
python main.py interactive --config config_hf_lightweight.yaml
```

### 2. Test Changes
```bash
# Test single functionality
python -c "
from tools.registry import create_default_registry
registry = create_default_registry()
print(registry.get_registry_info())
"
```

### 3. Full Integration Test
```bash
# Run comprehensive demo
python huggingface_example.py --demo
```

## 📁 Local File Structure After Setup

```
k8s-istio-agent/
├── venv/                           # Virtual environment
├── config_hf_quantized.yaml       # Generated config
├── ~/.cache/huggingface/          # Downloaded models
│   └── transformers/
│       ├── microsoft--DialoGPT-medium/
│       └── ...
├── logs/                          # Application logs
└── temp/                          # Temporary files
```

## 🎯 Next Steps

### Local Testing Complete ✅
1. **Basic functionality** - Agent responds to queries
2. **Tool integration** - kubectl commands work
3. **Model performance** - Acceptable response times

### Ready for Kubernetes Integration
```bash
# Test with local cluster
minikube start
kubectl apply -f k8s/rbac.yaml
python main.py interactive --config config_hf_quantized.yaml
```

### Deploy to Development Environment
```bash
# Build container
docker build -t k8s-istio-agent:dev .

# Test container locally
docker run -p 8080:8080 k8s-istio-agent:dev
```

## 💡 Tips for Best Experience

### 1. Model Selection
- **Start with `medium`** - best balance of quality/performance
- **Use quantization** - significantly reduces memory usage
- **GPU recommended** - 3-5x faster than CPU

### 2. Configuration Tuning
```yaml
# For faster responses (lower quality)
temperature: 0.5
max_length: 512

# For better quality (slower)
temperature: 0.8
max_length: 2048
```

### 3. Resource Monitoring
```bash
# Monitor resource usage
htop  # or Activity Monitor on macOS

# Monitor GPU usage (if available)
nvidia-smi -l 1
```

### 4. Debugging
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py interactive --config config_hf_quantized.yaml
```

---

**🎉 You're ready to test the HuggingFace-powered K8s troubleshooting agent!**

For questions or issues, check the main README.md or create an issue in the repository.