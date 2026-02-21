"""FastAPI server exposing prediction-market agents over HTTP.

Start:
    cd agents
    python3 -m uvicorn api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from research_agent import AgentConfig, ResearchAgent, ResearchInput, ResearchOutput
from risk_management_agent import (
    RiskAgentConfig,
    RiskManagementAgent,
    RiskManagementInput,
    RiskAnalysisOutput,
)

load_dotenv()

app = FastAPI(
    title="Polymarket Agent API",
    description="Research and risk management agents for prediction markets, powered by GPT-5.1",
    version="1.1.0",
)

# Allow the MCP server (or any local dev tool) to call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Quick health check so the MCP can verify the server is up."""
    return {"status": "ok"}


@app.post("/research", response_model=ResearchOutput)
async def research(
    body: ResearchInput,
    model: str = Query("gpt-5.1", description="OpenAI model to use"),
    timeout: float = Query(180.0, description="Total pipeline timeout in seconds"),
) -> ResearchOutput:
    """Run the full research pipeline on the provided events.

    Accepts a JSON body with ``main_event`` (optional) and ``sub_events``
    (required).  Returns structured research with summaries, sentiment,
    news links, and cross-event synthesis.

    Typical response time: ~1-2 minutes depending on number of sub-events.
    """
    config = AgentConfig(model=model, total_timeout=timeout)
    agent = ResearchAgent(config=config)
    return await agent.run(body)


@app.post("/risk", response_model=RiskAnalysisOutput)
async def risk_analysis(
    body: RiskManagementInput,
    model: str = Query("gpt-5.1", description="OpenAI model to use"),
    timeout: float = Query(90.0, description="Total pipeline timeout in seconds"),
) -> RiskAnalysisOutput:
    """Generate trading signals for prediction markets based on research.

    Accepts the full research agent output plus main event and markets.
    The research output is automatically preprocessed to extract what the
    LLM needs, then markets are analysed in parallel batches and
    reconciled for cross-market consistency.

    Typical response time: ~25-40 seconds for 20 markets.
    """
    config = RiskAgentConfig(model=model, total_timeout=timeout)
    agent = RiskManagementAgent(config=config)
    return await agent.run(body)
