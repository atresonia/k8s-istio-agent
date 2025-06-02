#!/usr/bin/env python3
"""
Example: Using HuggingFace LLM for Kubernetes Troubleshooting

This demonstrates how to configure and use different HuggingFace models
for troubleshooting scenarios.
"""
import asyncio
import yaml
from pathlib import Path

# Configuration examples for different HuggingFace models

# 1. Lightweight model for basic troubleshooting (good for CPU-only environments)
LIGHTWEIGHT_CONFIG = {
    "llm": {
        "provider": "huggingface",
        "config": {
            "model_name": "microsoft/DialoGPT-small",  # ~117M parameters
            "device": "cpu",
            "torch_dtype": "float32",
            "max_length": 512,
            "temperature": 0.7,
            "do_sample": True
        }
    }
}

# 2. Medium model with quantization (balanced performance/resources)
QUANTIZED_CONFIG = {
    "llm": {
        "provider": "huggingface",
        "config": {
            "model_name": "microsoft/DialoGPT-medium",  # ~345M parameters
            "device": "auto",
            "torch_dtype": "auto",
            "load_in_8bit": True,  # Reduces memory usage by ~50%
            "max_length": 1024,
            "temperature": 0.7,
            "do_sample": True
        }
    }
}

# 3. Code-focused model for technical troubleshooting
CODE_FOCUSED_CONFIG = {
    "llm": {
        "provider": "huggingface",
        "config": {
            "model_name": "microsoft/codebert-base",  # Good for code/config analysis
            "device": "auto",
            "torch_dtype": "float16",
            "max_length": 2048,
            "temperature": 0.5,  # Lower temperature for more focused responses
            "do_sample": True
        }
    }
}

# 4. Large model with 4-bit quantization (best quality with reasonable resources)
LARGE_QUANTIZED_CONFIG = {
    "llm": {
        "provider": "huggingface",
        "config": {
            "model_name": "microsoft/DialoGPT-large",  # ~762M parameters
            "device": "auto",
            "torch_dtype": "auto",
            "load_in_4bit": True,  # Maximum compression
            "max_length": 2048,
            "temperature": 0.7,
            "do_sample": True
        }
    }
}

async def demo_huggingface_usage():
    """Demonstrate HuggingFace provider usage"""
    
    # Import our components
    from llm.provider import LLMFactory, Message
    from tools.registry import create_default_registry
    from agent.controller import AgentController
    
    print("HuggingFace LLM Demo for K8s Troubleshooting")
    print("=" * 50)
    
    # Choose configuration based on your environment
    config = QUANTIZED_CONFIG  # Good balance for most systems
    
    try:
        # Initialize HuggingFace provider
        print("📦 Loading HuggingFace model...")
        llm_config = config["llm"]["config"]
        llm_provider = LLMFactory.create_provider("huggingface", **llm_config)
        
        # Show model info
        model_info = llm_provider.get_model_info()
        print(f"✅ Model loaded: {model_info['model_name']}")
        print(f"   Parameters: {model_info.get('num_parameters', 'unknown'):,}")
        print(f"   Device: {model_info.get('device', 'unknown')}")
        print(f"   Quantized: {model_info.get('quantized', False)}")
        
        # Initialize tools and agent
        tool_registry = create_default_registry()
        agent = AgentController(llm_provider, tool_registry)
        
        # Test troubleshooting scenarios
        test_scenarios = [
            {
                "query": "My pods are not starting. Can you help me investigate?",
                "description": "Basic pod troubleshooting"
            },
            {
                "query": "I'm seeing service connectivity issues between my frontend and backend",
                "description": "Service mesh connectivity"
            },
            {
                "query": "Check the health of my cluster resources",
                "description": "General health check"
            }
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n🔍 Scenario {i}: {scenario['description']}")
            print(f"Query: '{scenario['query']}'")
            print("-" * 30)
            
            # Process the query
            response = await agent.process_query(scenario['query'])
            
            # Display truncated response for demo
            lines = response.split('\n')
            preview = '\n'.join(lines[:5])
            if len(lines) > 5:
                preview += f"\n... ({len(lines) - 5} more lines)"
            
            print(f"Response preview:\n{preview}")
            print()
            
            # Reset for next scenario
            agent.reset_conversation()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure you have sufficient memory (4GB+ recommended)")
        print("2. For CPU-only: use 'device': 'cpu' and 'torch_dtype': 'float32'")
        print("3. Enable quantization: 'load_in_8bit': True or 'load_in_4bit': True")
        print("4. Try smaller models: DialoGPT-small or distilgpt2")

def create_config_file(config_type: str = "quantized"):
    """Create a configuration file for HuggingFace usage"""
    
    configs = {
        "lightweight": LIGHTWEIGHT_CONFIG,
        "quantized": QUANTIZED_CONFIG,
        "code_focused": CODE_FOCUSED_CONFIG,
        "large": LARGE_QUANTIZED_CONFIG
    }
    
    if config_type not in configs:
        raise ValueError(f"Unknown config type. Available: {list(configs.keys())}")
    
    # Complete configuration with other sections
    full_config = {
        **configs[config_type],
        "kubernetes": {"namespace": "default"},
        "istio": {"namespace": "istio-system"},
        "tools": {"enabled": ["kubectl", "istio", "logs"]},
        "logging": {"level": "INFO"},
        "agent": {
            "max_iterations": 5,
            "conversation_memory": 10
        }
    }
    
    config_file = f"config_hf_{config_type}.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(full_config, f, default_flow_style=False)
    
    print(f"📝 Created configuration file: {config_file}")
    return config_file

def check_system_requirements():
    """Check if system can run HuggingFace models"""
    import torch
    import psutil
    
    print("🔧 System Requirements Check")
    print("=" * 30)
    
    # Memory check
    memory_gb = psutil.virtual_memory().total / (1024**3)
    print(f"RAM: {memory_gb:.1f} GB")
    
    if memory_gb < 4:
        print("⚠️  Warning: Less than 4GB RAM. Consider using quantization or smaller models.")
    elif memory_gb >= 8:
        print("✅ Sufficient RAM for medium/large models")
    else:
        print("✅ Sufficient RAM for small/medium models")
    
    # GPU check
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
            print(f"GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")
        print("✅ CUDA available - can use GPU acceleration")
    else:
        print("ℹ️  No CUDA GPU detected - will use CPU")
    
    # Recommendations
    print("\n💡 Recommendations:")
    if memory_gb < 4:
        print("   • Use DialoGPT-small with CPU")
        print("   • Enable load_in_8bit: true")
    elif memory_gb < 8:
        print("   • Use DialoGPT-medium with quantization")
        print("   • Try load_in_8bit: true")
    else:
        print("   • Can use DialoGPT-large")
        print("   • Try load_in_4bit for even better performance")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HuggingFace LLM Demo")
    parser.add_argument("--demo", action="store_true", help="Run demo")
    parser.add_argument("--config", choices=["lightweight", "quantized", "code_focused", "large"], 
                       help="Create configuration file")
    parser.add_argument("--check", action="store_true", help="Check system requirements")
    
    args = parser.parse_args()
    
    if args.check:
        check_system_requirements()
    elif args.config:
        create_config_file(args.config)
    elif args.demo:
        asyncio.run(demo_huggingface_usage())
    else:
        print("HuggingFace K8s Troubleshooting Agent")
        print("Usage:")
        print("  python huggingface_example.py --check     # Check system requirements")
        print("  python huggingface_example.py --config quantized  # Create config file")
        print("  python huggingface_example.py --demo      # Run demo")
        print()
        check_system_requirements()