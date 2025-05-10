# Orchestrator main application 
from fastapi import FastAPI
from pydantic import BaseModel
import httpx

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Placeholder for future Next.js server base URL
NEXTJS_SERVER_BASE_URL = "http://localhost:3000/api/internal"

# Placeholder for microservice URLs
DISCORD_SERVICE_URL = "http://localhost:8001"
GDRIVE_SERVICE_URL = "http://localhost:8002"
TEAMSPEAK_SERVICE_URL = "http://localhost:8003"

class DiscordLinkRequest(BaseModel):
    discord_id: str

@app.post("/user/link/discord")
async def link_discord_account(request: DiscordLinkRequest):
    discord_id = request.discord_id
    print(f"Orchestrator: Received request to link Discord ID: {discord_id}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{DISCORD_SERVICE_URL}/user/{discord_id}/roles")
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            user_roles_data = response.json()
            print(f"Orchestrator: Roles received from Discord service: {user_roles_data}")
            
            # TODO: Next steps would be:
            # 1. Send user_roles_data to Next.js server to store/update in DB
            #    e.g., await client.post(f"{NEXTJS_SERVER_BASE_URL}/user/update_discord_info", json=user_roles_data)
            # 2. If Google/Teamspeak are already linked, fetch mappings and update their access.

            return user_roles_data
        except httpx.HTTPStatusError as exc:
            print(f"Orchestrator: HTTP error occurred while calling Discord service: {exc.response.status_code} - {exc.response.text}")
            # Forward the error or return a custom error message
            return {"error": "Failed to retrieve roles from Discord service", "details": exc.response.text, "status_code": exc.response.status_code}
        except httpx.RequestError as exc:
            print(f"Orchestrator: Request error occurred while calling Discord service: {exc}")
            return {"error": "Failed to connect to Discord service", "details": str(exc)}

# Example of how you might run this (for development):
# uvicorn orchestrator.main:app --reload --port 8000 