# Google Drive microservice main application 

from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gdrive_service"}

# Example of how you might run this (for development):
# uvicorn microservices.gdrive_service.main:app --reload --port 8002 