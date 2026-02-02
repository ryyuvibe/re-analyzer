"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import analysis, properties, investor, market, comparison

app = FastAPI(
    title="RE Analyzer",
    description="Real Estate Investment Analysis Tool",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router)
app.include_router(properties.router)
app.include_router(investor.router)
app.include_router(market.router)
app.include_router(comparison.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
