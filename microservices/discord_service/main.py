# Discord microservice main application 

from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "discord_service"}

@app.get("/user/{discord_id}/roles")
async def get_discord_user_roles(discord_id: str):
    # In a real scenario, you'd use discord.py here to fetch actual roles
    # For now, returning mock data
    print(f"Discord service: Received request for roles of user {discord_id}")
    mock_roles = [
        {"id": "role_id_1", "name": "Member"},
        {"id": "role_id_2", "name": "Moderator"}
    ]
    return {"discord_id": discord_id, "roles": mock_roles}

# Example of how you might run this (for development):
# uvicorn microservices.discord_service.main:app --reload --port 8001 