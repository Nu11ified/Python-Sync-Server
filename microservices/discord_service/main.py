# Discord microservice main application 

import discord
from discord.ext import commands
from fastapi import FastAPI
import asyncio
import os
import httpx
import time
from typing import List, Dict

# Configuration - Ideally, use environment variables or a config file
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000") # Default for local dev
ORCHESTRATOR_ROLE_UPDATE_HOOK_URL = f"{ORCHESTRATOR_URL}/internal/hooks/discord_role_change"

# FastAPI App
app = FastAPI()

# Discord Bot Setup
intents = discord.Intents.default()
intents.members = True  # Required for on_member_update to receive member changes
intents.message_content = True # Optional: if you plan to add message-based commands

bot = commands.Bot(command_prefix="!", intents=intents) # command_prefix is arbitrary if not used

# --- In-memory cache for roles ---
_roles_cache: Dict = {"data": None, "timestamp": 0}
ROLES_CACHE_TTL = 300  # 5 minutes in seconds

@bot.event
async def on_ready():
    print(f'Discord bot logged in as {bot.user.name} (ID: {bot.user.id})')
    print("------")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles != after.roles:
        changed_roles = [role for role in after.roles if role not in before.roles] + \
                        [role for role in before.roles if role not in after.roles]
        
        if not changed_roles: # Should not happen if before.roles != after.roles but as a safeguard
            return

        print(f"Role change detected for {after.name}#{after.discriminator} (ID: {after.id}) in guild {after.guild.name}")
        
        new_role_info = [{'id': str(role.id), 'name': role.name} for role in after.roles]
        payload = {
            "discord_id": str(after.id),
            "guild_id": str(after.guild.id), # Good to include for context
            "roles": new_role_info
        }

        print(f"Notifying orchestrator about role update for {after.id}: {payload}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(ORCHESTRATOR_ROLE_UPDATE_HOOK_URL, json=payload)
                response.raise_for_status() # Raise an exception for bad status codes
                print(f"Successfully notified orchestrator for {after.id}. Status: {response.status_code}")
        except httpx.HTTPStatusError as e:
            print(f"Error notifying orchestrator for {after.id}: HTTP {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"Error notifying orchestrator for {after.id}: Request failed - {str(e)}")
        except Exception as e:
            print(f"An unexpected error occurred while notifying orchestrator for {after.id}: {str(e)}")

# --- FastAPI Endpoints (kept from previous setup) ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "discord_service"}

@app.get("/user/{discord_id}/roles")
async def get_discord_user_roles(discord_id: str):
    # This endpoint might still be useful for an initial fetch when a user links their account,
    # or if the bot isn't in the specific guild yet/loses connection.
    # For a live bot, this would ideally fetch from the bot's cache or directly query Discord API.
    
    # For now, it can try to find the user in the bot's guilds if the bot is running
    if not bot.is_ready():
        return {"error": "Bot is not ready or not connected.", "discord_id": discord_id, "roles": []}

    try:
        user_id_int = int(discord_id)
    except ValueError:
        return {"error": "Invalid Discord ID format.", "discord_id": discord_id}

    # This is a simplified lookup. A real implementation might need to search across all guilds
    # or have a more direct way to get a user if you know their ID globally.
    member = None
    for guild in bot.guilds:
        fetched_member = guild.get_member(user_id_int)
        if fetched_member:
            member = fetched_member
            break
    
    if member:
        current_roles = [{'id': str(role.id), 'name': role.name} for role in member.roles]
        print(f"Discord service: Fetched roles for user {discord_id} via API endpoint: {current_roles}")
        return {"discord_id": discord_id, "roles": current_roles}
    else:
        # If user not found in bot's cache, could fall back to mock or error
        print(f"Discord service: User {discord_id} not found in bot's guilds for API endpoint request.")
        return {"error": "User not found in accessible guilds.", "discord_id": discord_id, "roles": []}

@app.get("/roles")
async def get_all_discord_roles():
    now = time.time()
    if _roles_cache["data"] is not None and (now - _roles_cache["timestamp"] < ROLES_CACHE_TTL):
        return {"cached": True, "roles": _roles_cache["data"]}

    if not bot.is_ready():
        return {"error": "Bot is not ready or not connected.", "roles": []}

    all_roles = []
    for guild in bot.guilds:
        for role in guild.roles:
            # Exclude @everyone (which is always the first role)
            if role.is_default():
                continue
            all_roles.append({
                "id": str(role.id),
                "name": role.name,
                "guild_id": str(guild.id),
                "guild_name": guild.name
            })
    _roles_cache["data"] = all_roles
    _roles_cache["timestamp"] = now
    return {"cached": False, "roles": all_roles}

# --- Bot and FastAPI App Lifespan Management ---
async def run_bot():
    try:
        if not DISCORD_BOT_TOKEN:
            print("Error: DISCORD_BOT_TOKEN environment variable not set. Bot will not start.")
            return
        await bot.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"Error starting Discord bot: {e}")
        # Optionally, re-raise or handle to shut down FastAPI app if bot is critical

@app.on_event("startup")
async def startup_event():
    print("FastAPI app started. Attempting to start Discord bot...")
    asyncio.create_task(run_bot())

@app.on_event("shutdown")
async def shutdown_event():
    print("FastAPI app shutting down. Attempting to close Discord bot connection...")
    if bot.is_ready(): # is_ready() might be more appropriate than is_closed() before logout
        await bot.close()
    print("Discord bot connection closed.")

# To run this combined service:
# 1. Set DISCORD_BOT_TOKEN environment variable.
# 2. Run: uvicorn microservices.discord_service.main:app --reload --port 8001 