#!/usr/bin/env python3
"""
Main entry point for the Kubernetes & Istio Troubleshooting Agent
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

import yaml
import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from llm.provider import LLMFactory
from tools.registry import create_default_registry
from agent.controller import AgentController

console = Console()
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if not Path(config_path).exists():
        # Create default config
        default_config = {
            "llm": {
                "provider": "huggingface",
                "config": {
                    "model_name": "microsoft/DialoGPT-medium",
                    "device": "auto",
                    "max_length": 1024,
                    "temperature": 0.7
                }
            },
            "kubernetes": {
                "namespace": "default"
            },
            "logging": {
                "level": "INFO"
            },
            "agent": {
                "max_iterations": 5,
                "conversation_memory": 10
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        console.print(f"[yellow]Created default config at {config_path}[/yellow]")
        return default_config
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_logging(config: Dict[str, Any]):
    """Setup logging configuration"""
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO"))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

class TroubleshootingAgent:
    """Main application class"""
    
    def __init__(self, config_path: str = "config.yaml", namespace: str = "default"):
        self.config = load_config(config_path)
        setup_logging(self.config)
        self.namespace = namespace
        # Initialize components
        self._init_llm_provider()
        self._init_tools()
        self._init_agent()
    
    def _init_llm_provider(self):
        """Initialize LLM provider"""
        llm_config = self.config["llm"]
        provider_name = llm_config["provider"]
        provider_config = llm_config["config"]
        
        try:
            self.llm_provider = LLMFactory.create_provider(provider_name, **provider_config)
            console.print(f"[green]✓[/green] Initialized {provider_name} LLM provider")
            
            # Log model info
            model_info = self.llm_provider.get_model_info()
            logger.info(f"LLM Provider Info: {model_info}")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to initialize LLM provider: {e}")
            raise
    
    def _init_tools(self):
        """Initialize tool registry"""
        try:
            self.tool_registry = create_default_registry()
            tools = self.tool_registry.list_tools()
            console.print(f"[green]✓[/green] Registered {len(tools)} tools")
            
            for tool in tools:
                logger.info(f"Available tool: {tool.name} ({tool.category.value})")
                
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to initialize tools: {e}")
            raise
    
    def _init_agent(self):
        """Initialize agent controller"""
        agent_config = self.config.get("agent", {})
        
        self.agent = AgentController(
            llm_provider=self.llm_provider,
            tool_registry=self.tool_registry,
            max_iterations=agent_config.get("max_iterations", 5),
            conversation_memory=agent_config.get("conversation_memory", 10)
        )
        
        console.print("[green]✓[/green] Agent controller initialized")
    
    async def run_interactive(self):
        """Run interactive troubleshooting session"""
        console.print(Panel.fit(
            "[bold blue]🔧 Kubernetes & Istio Troubleshooting Agent[/bold blue]\n"
            "I can help you diagnose and resolve issues with:\n"
            "• Pod startup and runtime problems\n"
            "• Service connectivity issues\n"
            "• Istio service mesh configuration\n"
            "• Resource constraints and performance\n\n"
            "[dim]Type 'exit' to quit, 'reset' to start fresh, 'help' for commands[/dim]",
            title="Welcome"
        ))
        
        namespace = self.config.get("kubernetes", {}).get("namespace", "default")
        console.print(f"[dim]Default namespace: {namespace}[/dim]\n")
        
        while True:
            try:
                # Get user input
                user_input = console.input("[bold green]🤖 What can I help you troubleshoot?[/bold green] ")
                
                if user_input.lower() == 'exit':
                    console.print("[yellow]Goodbye! 👋[/yellow]")
                    break
                elif user_input.lower() == 'reset':
                    self.agent.reset_conversation()
                    console.print("[yellow]Conversation reset[/yellow]")
                    continue
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower().startswith('namespace '):
                    namespace = user_input[10:].strip()
                    console.print(f"[yellow]Switched to namespace: {namespace}[/yellow]")
                    continue
                elif not user_input.strip():
                    continue
                
                # Process query
                console.print("\n[dim]🔍 Analyzing your issue...[/dim]")
                
                with console.status("[bold green]Investigating..."):
                    response = await self.agent.process_query(user_input, namespace)
                
                # Display response
                console.print("\n" + "="*80)
                console.print(Text(response, style="white"))
                console.print("="*80 + "\n")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.exception("Unexpected error in interactive mode")
    
    async def run_single_query(self, query: str, namespace: str = "default") -> str:
        """Run a single query and return response"""
        return await self.agent.process_query(query, namespace)
    
    def _show_help(self):
        """Show help information"""
        help_text = """
[bold]Available Commands:[/bold]
• [green]exit[/green] - Quit the application
• [green]reset[/green] - Reset conversation history
• [green]namespace <name>[/green] - Switch default namespace
• [green]help[/green] - Show this help

[bold]Example Queries:[/bold]
• "My pods are not starting in the frontend namespace"
• "Service connectivity issues between microservices"
• "Istio proxy shows configuration errors"
• "High memory usage on worker nodes"
• "Check if all services are running properly"

[bold]Tips:[/bold]
• Be specific about symptoms and affected resources
• Mention the namespace if different from default
• Include error messages you've observed
• I'll use kubectl and istio tools to investigate systematically
        """
        console.print(Panel(help_text, title="Help"))

# CLI Interface
@click.group()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, config, debug):
    """Kubernetes & Istio Troubleshooting Agent"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

@cli.command()
@click.option('--namespace', default='default', help='Kubernetes namespace')
@click.option('--config', help='Override configuration file path')
@click.pass_context
def interactive(ctx, namespace, config):
    """Run interactive troubleshooting session"""
    try:
        config_path = config or ctx.obj['config']
        ns = namespace or ctx.obj['namespace']
        agent = TroubleshootingAgent(config_path, ns)
        agent.namespace = namespace
        asyncio.run(agent.run_interactive())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye! 👋[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to start agent: {e}[/red]")
        sys.exit(1)

@cli.command()
@click.argument('query')
@click.option('--namespace', default='default', help='Kubernetes namespace')
@click.option('--config', help='Override configuration file path')
@click.pass_context
def query(ctx, query, namespace, config):
    """Run a single troubleshooting query"""
    try:
        config_path = config or ctx.obj['config']
        agent = TroubleshootingAgent(config_path)
        response = asyncio.run(agent.run_single_query(query, namespace))
        console.print(response)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

@cli.command()
@click.option('--config', help='Override configuration file path')
@click.pass_context
def info(ctx, config):
    """Show agent and tool information"""
    try:
        config_path = config or ctx.obj['config']
        agent = TroubleshootingAgent(config_path)
        
        # LLM Provider Info
        model_info = agent.llm_provider.get_model_info()
        console.print("\n[bold]LLM Provider:[/bold]")
        for key, value in model_info.items():
            console.print(f"  {key}: {value}")
        
        # Tools Info
        registry_info = agent.tool_registry.get_registry_info()
        console.print(f"\n[bold]Tools Registry:[/bold]")
        console.print(f"  Total tools: {registry_info['total_tools']}")
        console.print(f"  Enabled tools: {registry_info['enabled_tools']}")
        
        for category, info in registry_info['categories'].items():
            if info['tools']:
                console.print(f"\n  [bold]{category.title()}:[/bold]")
                for tool_name in info['tools']:
                    status = "✓" if tool_name in [t.name for t in agent.tool_registry.list_tools()] else "✗"
                    console.print(f"    {status} {tool_name}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

@cli.command()
def web():
    """Start web interface (requires web dependencies)"""
    try:
        from web.app import create_app
        import uvicorn
        
        app = create_app()
        console.print("[green]Starting web interface on http://localhost:8080[/green]")
        uvicorn.run(app, host="0.0.0.0", port=8080)
        
    except ImportError:
        console.print("[red]Web interface dependencies not installed. Install with: pip install fastapi uvicorn jinja2[/red]")
    except Exception as e:
        console.print(f"[red]Failed to start web interface: {e}[/red]")

if __name__ == "__main__":
    cli()