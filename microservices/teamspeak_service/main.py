# Teamspeak microservice main application 
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Attempt to load ts3 library
try:
    import ts3
    TS3_LIB_AVAILABLE = True
except ImportError:
    TS3_LIB_AVAILABLE = False
    print("Teamspeak Service WARNING: ts3 library not found. Real TS3 operations will fail. Install ts3 (python-teamspeak3).")

load_dotenv()

app = FastAPI()

# --- Configuration (should come from environment variables or a config file) ---
# Example: Ensure these are set in your environment for a real deployment
TS_SERVER_HOST = os.getenv("TS_SERVER_HOST", "localhost")
TS_SERVER_QUERY_PORT = int(os.getenv("TS_SERVER_QUERY_PORT", "10011"))
TS_VIRTUAL_SERVER_ID = int(os.getenv("TS_VIRTUAL_SERVER_ID", "1")) # Default virtual server ID
TS_QUERY_LOGIN_NAME = os.getenv("TS_QUERY_LOGIN_NAME", "serveradmin")
TS_QUERY_LOGIN_PASSWORD = os.getenv("TS_QUERY_LOGIN_PASSWORD")

# --- Pydantic Models for Request Bodies ---
class UserGroupActionRequest(BaseModel):
    teamspeak_unique_id: str  # The user's permanent unique ID (client_unique_identifier)
    server_group_id: str      # The ID of the server group to add/remove (sgid)

# --- Helper to get TS Connection (basic implementation) ---
def get_ts_connection():
    if not TS3_LIB_AVAILABLE or not TS_QUERY_LOGIN_PASSWORD:
        print("Teamspeak Service: Library not available or TS_QUERY_LOGIN_PASSWORD not set.")
        return None
    try:
        # The TS3Connection should be properly managed. 
        # For a production service, consider a more robust connection management strategy
        # (e.g., a pool, or ensuring it's thread-safe if FastAPI runs multiple workers).
        # Using a new connection per request for simplicity here, but can be inefficient.
        conn = ts3.query.TS3Connection(TS_SERVER_HOST, TS_SERVER_QUERY_PORT)
        conn.login(
            client_login_name=TS_QUERY_LOGIN_NAME,
            client_login_password=TS_QUERY_LOGIN_PASSWORD
        )
        conn.use(sid=TS_VIRTUAL_SERVER_ID)
        return conn
    except ts3.query.TS3QueryError as e:
        print(f"Teamspeak Service: Failed to connect/login: {e.resp.error.get('msg', 'Unknown TSQueryError')}")
        # Don't raise HTTPException here, let endpoint decide if it's critical for this specific call
        return None 
    except Exception as e:
        print(f"Teamspeak Service: General error establishing TS connection: {str(e)}")
        return None

# --- Service Endpoints ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "teamspeak_service"}

@app.post("/groups/add_user")
async def add_user_to_group(request: UserGroupActionRequest):
    print(f"Teamspeak Service: Request to ADD UID {request.teamspeak_unique_id} to group {request.server_group_id}")
    conn = get_ts_connection()
    if not conn:
        # Fallback to simulation if TS lib/creds are not set up or connection fails
        print("Teamspeak Service: Connection not available. Simulating success.")
        return {"status": "simulated_success_due_to_config_or_conn_error", "message": f"Simulated: User {request.teamspeak_unique_id} added to group {request.server_group_id}"}

    try:
        # 1. Get client database ID (cldbid) from unique ID (client_uid)
        resp_cldbid = conn.clientgetdbidfromuid(cluid=request.teamspeak_unique_id)
        if not resp_cldbid or not resp_cldbid.parsed:
            # clientgetdbidfromuid returns empty list if UID not found, not an error in py-ts3 v1.x
            # TS3QueryError: error id=512 msg=invalid\sclientUID (for invalid format)
            # error id=0 (empty response) if UID is valid format but not found.
            print(f"Teamspeak Service: Could not find cldbid for UID {request.teamspeak_unique_id}. Response: {resp_cldbid.parsed if resp_cldbid else 'None'}")
            raise HTTPException(status_code=404, detail=f"Client with unique ID {request.teamspeak_unique_id} not found on this virtual server.")
        
        client_db_id = resp_cldbid.parsed[0]['cldbid']
        
        # 2. Add user to server group
        conn.servergroupaddclient(sgid=request.server_group_id, cldbid=client_db_id)
        print(f"Teamspeak Service: Successfully ADDED UID {request.teamspeak_unique_id} (cldbid: {client_db_id}) to group {request.server_group_id}")
        return {"status": "success", "message": f"User {request.teamspeak_unique_id} added to group {request.server_group_id}"}
    except ts3.query.TS3QueryError as e:
        error_msg = e.resp.error.get('msg', 'Unknown TSQueryError')
        error_id = e.resp.error.get('id', '0')
        print(f"Teamspeak Service: TS3QueryError adding user: ID {error_id} - {error_msg}")
        # Example: error id=2568 msg=duplicate\sentry (already in group)
        if error_id == "2568": # Duplicate entry / already in group
             return {"status": "success_already_in_group", "message": f"User {request.teamspeak_unique_id} already in group {request.server_group_id}. Details: {error_msg}"}
        raise HTTPException(status_code=400, detail=f"Teamspeak Query Error: {error_msg} (ID: {error_id})")
    except Exception as e:
        print(f"Teamspeak Service: General error adding user to group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error in Teamspeak service: {str(e)}")
    finally:
        if conn: # Ensure conn was successfully created before trying to quit
            try:
                conn.quit() # Important to close the connection
            except: pass # Ignore errors on quit

@app.post("/groups/remove_user")
async def remove_user_from_group(request: UserGroupActionRequest):
    print(f"Teamspeak Service: Request to REMOVE UID {request.teamspeak_unique_id} from group {request.server_group_id}")
    conn = get_ts_connection()
    if not conn:
        print("Teamspeak Service: Connection not available. Simulating success.")
        return {"status": "simulated_success_due_to_config_or_conn_error", "message": f"Simulated: User {request.teamspeak_unique_id} removed from group {request.server_group_id}"}

    try:
        resp_cldbid = conn.clientgetdbidfromuid(cluid=request.teamspeak_unique_id)
        if not resp_cldbid or not resp_cldbid.parsed:
            print(f"Teamspeak Service: Could not find cldbid for UID {request.teamspeak_unique_id} for removal.")
            raise HTTPException(status_code=404, detail=f"Client with unique ID {request.teamspeak_unique_id} not found.")
        
        client_db_id = resp_cldbid.parsed[0]['cldbid']
        
        conn.servergroupdelclient(sgid=request.server_group_id, cldbid=client_db_id)
        print(f"Teamspeak Service: Successfully REMOVED UID {request.teamspeak_unique_id} (cldbid: {client_db_id}) from group {request.server_group_id}")
        return {"status": "success", "message": f"User {request.teamspeak_unique_id} removed from group {request.server_group_id}"}
    except ts3.query.TS3QueryError as e:
        error_msg = e.resp.error.get('msg', 'Unknown TSQueryError')
        error_id = e.resp.error.get('id', '0')
        print(f"Teamspeak Service: TS3QueryError removing user: ID {error_id} - {error_msg}")
        # Example: error id=1281 msg=database empty result set (user not in group, or group/user invalid for this action)
        if error_id == "1281": # Often means user was not in the group
             return {"status": "success_not_in_group", "message": f"User {request.teamspeak_unique_id} was not in group {request.server_group_id}, or group/user invalid. Details: {error_msg}"}
        raise HTTPException(status_code=400, detail=f"Teamspeak Query Error: {error_msg} (ID: {error_id})")
    except Exception as e:
        print(f"Teamspeak Service: General error removing user from group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error in Teamspeak service: {str(e)}")
    finally:
        if conn:
            try:
                conn.quit()
            except: pass

# Example of how you might run this (for development):
# Make sure TS_QUERY_LOGIN_PASSWORD and other TS_* env vars are set.
# uvicorn microservices.teamspeak_service.main:app --reload --port 8003 