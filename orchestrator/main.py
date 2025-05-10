# Orchestrator main application 
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import httpx
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Placeholder for future Next.js server base URL
NEXTJS_SERVER_BASE_URL = os.getenv("NEXTJS_SERVER_BASE_URL", "http://localhost:3000/api/internal")

# Placeholder for microservice URLs
DISCORD_SERVICE_URL = os.getenv("DISCORD_SERVICE_URL", "http://localhost:8001")
GDRIVE_SERVICE_URL = os.getenv("GDRIVE_SERVICE_URL", "http://localhost:8002")
TEAMSPEAK_SERVICE_URL = os.getenv("TEAMSPEAK_SERVICE_URL", "http://localhost:8003")

class DiscordLinkRequest(BaseModel):
    discord_id: str

class DiscordRoleInfo(BaseModel):
    id: str
    name: str

class DiscordRoleUpdatePayload(BaseModel):
    discord_id: str
    guild_id: str
    roles: List[DiscordRoleInfo]

class UserLinkedAccounts(BaseModel):
    discord_id: str
    internal_user_id: Optional[str] = None
    google_email: Optional[EmailStr] = None
    teamspeak_unique_id: Optional[str] = None
    is_google_linked: bool = False
    is_teamspeak_linked: bool = False

# Mocked data - In a real app, this would come from Next.js API
MOCK_ROLE_MAPPINGS: Dict[str, Dict[str, list]] = {
    # Discord Role ID : { gdrive: [...], teamspeak: [...] }
    "role_id_1": { # Example: "Member" role from discord_service mock
        "gdrive": [
            {"item_id": "folder_members_docs_id", "role": "reader"},
            {"item_id": "sheet_general_info_id", "role": "commenter"}
        ],
        "teamspeak": [
            {"group_id": "ts_group_member_id"}
        ]
    },
    "role_id_2": { # Example: "Moderator" role
        "gdrive": [
            {"item_id": "folder_moderator_tools_id", "role": "editor"}
        ],
        "teamspeak": [
            {"group_id": "ts_group_moderator_id"}
        ]
    }
    # Add more mappings as needed
}

async def _get_user_linked_accounts_details(discord_id: str) -> UserLinkedAccounts:
    print(f"Orchestrator: Fetching linked accounts for Discord ID {discord_id} from Next.js")
    if discord_id == "123456789": 
        return UserLinkedAccounts(
            discord_id=discord_id,
            internal_user_id="nextjs_user_abc",
            google_email="testuser@example.com",
            teamspeak_unique_id="test_ts_uid_xyz123",
            is_google_linked=True,
            is_teamspeak_linked=True
        )
    return UserLinkedAccounts(discord_id=discord_id, internal_user_id=f"nextjs_user_for_{discord_id}")

async def _get_role_mappings_from_nextjs(guild_id: str) -> Dict[str, Dict[str, list]]:
    print(f"Orchestrator: Fetching role mappings for guild {guild_id} from Next.js (using mock)")
    return MOCK_ROLE_MAPPINGS

async def _get_previous_discord_roles_from_nextjs(internal_user_id: str, guild_id: str) -> List[DiscordRoleInfo]:
    print(f"Orchestrator: Fetching PREVIOUS Discord roles for internal user {internal_user_id} in guild {guild_id} from Next.js")
    return []

async def _update_discord_roles_in_nextjs(internal_user_id: str, payload: DiscordRoleUpdatePayload):
    print(f"Orchestrator: Updating Discord roles in Next.js for internal user {internal_user_id} (simulated)")
    pass

async def _process_role_changes_and_update_services(
    linked_accounts: UserLinkedAccounts,
    guild_id: str,
    current_roles_info: List[DiscordRoleInfo],
    previous_roles_info: List[DiscordRoleInfo]
):
    print(f"Orchestrator: Processing role changes for Discord ID {linked_accounts.discord_id} in guild {guild_id}")

    role_mappings = await _get_role_mappings_from_nextjs(guild_id)
    if not role_mappings:
        print(f"Orchestrator: No role mappings found for guild {guild_id}. Skipping GDrive/Teamspeak updates.")
        return

    current_role_ids = {role.id for role in current_roles_info}
    previous_role_ids = {role.id for role in previous_roles_info}

    added_role_ids = current_role_ids - previous_role_ids
    removed_role_ids = previous_role_ids - current_role_ids

    async with httpx.AsyncClient() as client:
        for role_id in added_role_ids:
            mapping = role_mappings.get(role_id)
            if not mapping: continue

            if linked_accounts.is_google_linked and linked_accounts.google_email and "gdrive" in mapping:
                for perm_config in mapping["gdrive"]:
                    gdrive_payload = {
                        "user_email": linked_accounts.google_email,
                        "item_id": perm_config["item_id"],
                        "role": perm_config["role"]
                    }
                    try:
                        print(f"Orchestrator: GRANT GDrive: {gdrive_payload}")
                        response = await client.post(f"{GDRIVE_SERVICE_URL}/permissions/grant", json=gdrive_payload, timeout=10.0)
                        response.raise_for_status()
                        print(f"Orchestrator: GDrive grant successful for role {role_id}, item {perm_config['item_id']}: {response.json()}")
                    except httpx.HTTPStatusError as e_http:
                        print(f"Orchestrator: HTTPStatusError GDrive grant for role {role_id}, item {perm_config['item_id']}: {e_http.response.status_code} - {e_http.response.text}")
                    except httpx.RequestError as e_req:
                        print(f"Orchestrator: RequestError GDrive grant for role {role_id}, item {perm_config['item_id']}: {e_req}")
                    except Exception as e_gen:
                        print(f"Orchestrator: General Error GDrive grant for role {role_id}, item {perm_config['item_id']}: {e_gen}")
            
            if linked_accounts.is_teamspeak_linked and linked_accounts.teamspeak_unique_id and "teamspeak" in mapping:
                for group_config in mapping["teamspeak"]:
                    ts_payload = {
                        "teamspeak_unique_id": linked_accounts.teamspeak_unique_id,
                        "server_group_id": group_config["group_id"]
                    }
                    try:
                        print(f"Orchestrator: ADD Teamspeak group: {ts_payload}")
                        response = await client.post(f"{TEAMSPEAK_SERVICE_URL}/groups/add_user", json=ts_payload, timeout=10.0)
                        response.raise_for_status()
                        print(f"Orchestrator: Teamspeak add_user successful for role {role_id}, group {group_config['group_id']}: {response.json()}")
                    except httpx.HTTPStatusError as e_http:
                        print(f"Orchestrator: HTTPStatusError Teamspeak add_user for role {role_id}, group {group_config['group_id']}: {e_http.response.status_code} - {e_http.response.text}")
                    except httpx.RequestError as e_req:
                        print(f"Orchestrator: RequestError Teamspeak add_user for role {role_id}, group {group_config['group_id']}: {e_req}")
                    except Exception as e_gen:
                        print(f"Orchestrator: General Error Teamspeak add_user for role {role_id}, group {group_config['group_id']}: {e_gen}")

        for role_id in removed_role_ids:
            mapping = role_mappings.get(role_id)
            if not mapping: continue

            if linked_accounts.is_google_linked and linked_accounts.google_email and "gdrive" in mapping:
                for perm_config in mapping["gdrive"]:
                    gdrive_payload = {
                        "user_email": linked_accounts.google_email,
                        "item_id": perm_config["item_id"]
                    }
                    try:
                        print(f"Orchestrator: REVOKE GDrive: {gdrive_payload}")
                        response = await client.post(f"{GDRIVE_SERVICE_URL}/permissions/revoke", json=gdrive_payload, timeout=10.0)
                        response.raise_for_status()
                        print(f"Orchestrator: GDrive revoke successful for role {role_id}, item {perm_config['item_id']}: {response.json()}")
                    except httpx.HTTPStatusError as e_http:
                        print(f"Orchestrator: HTTPStatusError GDrive revoke for role {role_id}, item {perm_config['item_id']}: {e_http.response.status_code} - {e_http.response.text}")
                    except httpx.RequestError as e_req:
                        print(f"Orchestrator: RequestError GDrive revoke for role {role_id}, item {perm_config['item_id']}: {e_req}")
                    except Exception as e_gen:
                        print(f"Orchestrator: General Error GDrive revoke for role {role_id}, item {perm_config['item_id']}: {e_gen}")
            
            if linked_accounts.is_teamspeak_linked and linked_accounts.teamspeak_unique_id and "teamspeak" in mapping:
                for group_config in mapping["teamspeak"]:
                    ts_payload = {
                        "teamspeak_unique_id": linked_accounts.teamspeak_unique_id,
                        "server_group_id": group_config["group_id"]
                    }
                    try:
                        print(f"Orchestrator: REMOVE Teamspeak group: {ts_payload}")
                        response = await client.post(f"{TEAMSPEAK_SERVICE_URL}/groups/remove_user", json=ts_payload, timeout=10.0)
                        response.raise_for_status()
                        print(f"Orchestrator: Teamspeak remove_user successful for role {role_id}, group {group_config['group_id']}: {response.json()}")
                    except httpx.HTTPStatusError as e_http:
                        print(f"Orchestrator: HTTPStatusError Teamspeak remove_user for role {role_id}, group {group_config['group_id']}: {e_http.response.status_code} - {e_http.response.text}")
                    except httpx.RequestError as e_req:
                        print(f"Orchestrator: RequestError Teamspeak remove_user for role {role_id}, group {group_config['group_id']}: {e_req}")
                    except Exception as e_gen:
                        print(f"Orchestrator: General Error Teamspeak remove_user for role {role_id}, group {group_config['group_id']}: {e_gen}")

@app.post("/user/link/discord")
async def link_discord_account(request: DiscordLinkRequest):
    discord_id = request.discord_id
    print(f"Orchestrator: Linking Discord ID: {discord_id}")
    linked_accounts = await _get_user_linked_accounts_details(discord_id)
    if not linked_accounts.internal_user_id:
        print(f"Orchestrator: Critical - No internal_user_id found/created for discord_id {discord_id}")
        raise HTTPException(status_code=500, detail="User account could not be identified or created.")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{DISCORD_SERVICE_URL}/user/{discord_id}/roles")
            response.raise_for_status()
            discord_data = response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Orchestrator: HTTP error Discord service: {exc.response.status_code} - {exc.response.text}")
            raise HTTPException(status_code=exc.response.status_code, detail=f"Error from Discord service: {exc.response.text}")
        except httpx.RequestError as exc:
            print(f"Orchestrator: Request error Discord service: {exc}")
            raise HTTPException(status_code=503, detail=f"Failed to connect to Discord service: {str(exc)}")

    current_roles_info = [DiscordRoleInfo(**role) for role in discord_data.get("roles", [])]
    guild_id = discord_data.get("guild_id", "unknown_guild_id")
    if guild_id == "unknown_guild_id" and current_roles_info:
        print(f"Warning: guild_id not found in discord_data for user {discord_id}, but roles exist. Mappings might be inaccurate.")

    await _update_discord_roles_in_nextjs(linked_accounts.internal_user_id, DiscordRoleUpdatePayload(
        discord_id=discord_id, guild_id=guild_id, roles=current_roles_info
    ))
    previous_roles_info = []
    await _process_role_changes_and_update_services(
        linked_accounts=linked_accounts, guild_id=guild_id, 
        current_roles_info=current_roles_info, previous_roles_info=previous_roles_info
    )
    return discord_data

@app.post("/internal/hooks/discord_role_change")
async def handle_discord_role_change(payload: DiscordRoleUpdatePayload):
    print(f"Orchestrator: Hook for Discord role change: user {payload.discord_id}, guild {payload.guild_id}")
    linked_accounts = await _get_user_linked_accounts_details(payload.discord_id)
    if not linked_accounts.internal_user_id:
        print(f"Orchestrator: Critical - No internal_user_id for discord_id {payload.discord_id} during role update hook. Ignoring.")
        return {"status": "error", "message": "User not found internally."}

    previous_roles_info = await _get_previous_discord_roles_from_nextjs(linked_accounts.internal_user_id, payload.guild_id)
    await _process_role_changes_and_update_services(
        linked_accounts=linked_accounts, guild_id=payload.guild_id,
        current_roles_info=payload.roles, previous_roles_info=previous_roles_info
    )
    await _update_discord_roles_in_nextjs(linked_accounts.internal_user_id, payload)
    return {"status": "received", "message": "Discord role update acknowledged and processed."}

# Example of how you might run this (for development):
# uvicorn orchestrator.main:app --reload --port 8000 