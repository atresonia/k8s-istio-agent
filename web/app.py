"""
Web interface for the Kubernetes & Istio Troubleshooting Agent
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Import our agent components
import sys
sys.path.append(str(Path(__file__).parent.parent))

from llm.provider import LLMFactory
from tools.registry import create_default_registry
from agent.controller import AgentController

logger = logging.getLogger(__name__)

# Pydantic models for API
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    success: bool
    response: str
    error: str = ""

# Global agent instance
agent_controller = None

def create_app(config_path: str = "config.yaml") -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="K8s & Istio Troubleshooting Agent",
        description="AI-powered troubleshooting for Kubernetes and Istio",
        version="1.0.0"
    )
    
    # Setup templates
    template_dir = Path(__file__).parent / "templates"
    template_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=str(template_dir))
    
    # Setup static files (if needed)
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Initialize agent
    global agent_controller
    if agent_controller is None:
        agent_controller = _initialize_agent(config_path)
    
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Home page"""
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "agent_available": agent_controller is not None
        }
    
    @app.post("/api/query", response_model=QueryResponse)
    async def query_agent(request: QueryRequest):
        """Query the troubleshooting agent"""
        try:
            if not agent_controller:
                return QueryResponse(
                    success=False,
                    response="",
                    error="Agent not initialized"
                )
            
            response = await agent_controller.process_query(
                request.query, 
            )
            
            return QueryResponse(
                success=True,
                response=response
            )
        
        except Exception as e:
            logger.error(f"Query error: {e}")
            return QueryResponse(
                success=False,
                response="",
                error=str(e)
            )
    
    @app.get("/api/tools")
    async def get_tools():
        """Get available tools"""
        if not agent_controller:
            return {"error": "Agent not initialized"}
        
        tools = agent_controller.tools.list_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category.value,
                    "enabled": tool.enabled
                }
                for tool in tools
            ]
        }
    
    @app.get("/api/conversation")
    async def get_conversation():
        """Get conversation summary"""
        if not agent_controller:
            return {"error": "Agent not initialized"}
        
        return agent_controller.get_conversation_summary()
    
    @app.post("/api/reset")
    async def reset_conversation():
        """Reset conversation"""
        if not agent_controller:
            return {"error": "Agent not initialized"}
        
        agent_controller.reset_conversation()
        return {"success": True}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time interaction"""
        await websocket.accept()
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data["type"] == "query":
                    # Process query
                    query = message_data["query"]
                    
                    if agent_controller:
                        # Send typing indicator
                        await websocket.send_text(json.dumps({
                            "type": "typing",
                            "message": "Agent is analyzing..."
                        }))
                        
                        try:
                            response = await agent_controller.process_query(query)
                            
                            await websocket.send_text(json.dumps({
                                "type": "response",
                                "response": response,
                                "success": True
                            }))
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "error": str(e),
                                "success": False
                            }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "error": "Agent not initialized",
                            "success": False
                        }))
                
                elif message_data["type"] == "reset":
                    if agent_controller:
                        agent_controller.reset_conversation()
                        await websocket.send_text(json.dumps({
                            "type": "reset_confirm",
                            "message": "Conversation reset"
                        }))
        
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    return app

def _initialize_agent(config_path: str) -> AgentController:
    """Initialize the agent controller"""
    try:
        # Load configuration
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize LLM provider
        llm_config = config["llm"]
        llm_provider = LLMFactory.create_provider(
            llm_config["provider"],
            **llm_config["config"]
        )
        
        # Initialize tools
        tool_registry = create_default_registry()
        
        # Initialize agent
        agent_config = config.get("agent", {})
        agent = AgentController(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            max_iterations=agent_config.get("max_iterations", 5),
            conversation_memory=agent_config.get("conversation_memory", 10)
        )
        
        logger.info("Agent initialized successfully for web interface")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return None

if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080)