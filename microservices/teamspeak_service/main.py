# Teamspeak microservice main application 
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "teamspeak_service"}

# Example of how you might run this (for development):
# uvicorn microservices.teamspeak_service.main:app --reload --port 8003 