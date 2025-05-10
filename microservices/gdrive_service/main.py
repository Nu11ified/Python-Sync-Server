# Google Drive microservice main application 

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
import time
from typing import List, Dict

# Attempt to load google client libraries
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    print("GDrive Service WARNING: Google API libraries not found. Real GDrive operations will fail. Install google-api-python-client and google-auth.")

load_dotenv() 

app = FastAPI()

# --- Configuration ---
# GOOGLE_APPLICATION_CREDENTIALS environment variable should be set to the path of your service account key file.
# This is automatically used by the Google client library if set.
# GDRIVE_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GDRIVE_SERVICE_ACCOUNT_KEY_PATH") # Alternative if not using GOOGLE_APPLICATION_CREDENTIALS directly

# --- Pydantic Models for Request Bodies ---
class GrantPermissionRequest(BaseModel):
    user_email: EmailStr
    item_id: str
    role: str # Examples: "reader", "writer", "commenter"

class RevokePermissionRequest(BaseModel):
    user_email: EmailStr
    item_id: str

# --- In-memory cache for items ---
_items_cache: Dict = {"data": None, "timestamp": 0}
ITEMS_CACHE_TTL = 600  # 10 minutes in seconds

def get_drive_service():
    if not GOOGLE_LIBS_AVAILABLE:
        return None
    try:
        # If GOOGLE_APPLICATION_CREDENTIALS is set, it's used automatically.
        # If using GDRIVE_SERVICE_ACCOUNT_KEY_PATH, load manually:
        # creds = service_account.Credentials.from_service_account_file(GDRIVE_SERVICE_ACCOUNT_KEY_PATH, scopes=['https://www.googleapis.com/auth/drive'])
        # For simplicity, relying on GOOGLE_APPLICATION_CREDENTIALS for now.
        creds = None # Will use ADC (Application Default Credentials) if GOOGLE_APPLICATION_CREDENTIALS is set
        # Explicitly define scopes if not broadly configured for the service account key (though often they are)
        # For managing permissions, 'https://www.googleapis.com/auth/drive' is usually sufficient if the service account has editor rights on the items.
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             creds = service_account.Credentials.from_service_account_file(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS"), 
                scopes=['https://www.googleapis.com/auth/drive']
            )
        else:
            print("GDrive Service WARNING: GOOGLE_APPLICATION_CREDENTIALS not set. Real GDrive operations will fail.")
            return None

        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"GDrive Service: Error building Drive service: {e}")
        return None

# --- Service Endpoints ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gdrive_service"}

@app.post("/permissions/grant")
async def grant_drive_permission(request: GrantPermissionRequest):
    print(f"GDrive Service: Request to GRANT {request.role} to {request.user_email} on {request.item_id}")
    drive_service = get_drive_service()
    if not drive_service:
        print("GDrive Service: Drive service not available. Simulating success.")
        # Fallback to simulation if Google libs/creds are not set up, to not block testing other parts.
        return {"status": "simulated_success_due_to_config", "message": f"Simulated: Permission {request.role} granted to {request.user_email} for item {request.item_id}"}

    try:
        permission = {
            'type': 'user',
            'role': request.role,
            'emailAddress': request.user_email
        }
        drive_service.permissions().create(
            fileId=request.item_id,
            body=permission,
            fields='id',
            sendNotificationEmail=False 
        ).execute()
        print(f"GDrive Service: Successfully granted {request.role} to {request.user_email} on {request.item_id}")
        return {"status": "success", "message": f"Permission {request.role} granted to {request.user_email} for item {request.item_id}"}
    except HttpError as e:
        print(f"GDrive Service: Google API HttpError granting permission: {e.status_code} - {e.content}")
        raise HTTPException(status_code=e.status_code, detail=f"Google API Error: {e.content.decode() if isinstance(e.content, bytes) else str(e.content)}")
    except Exception as e:
        print(f"GDrive Service: General error granting permission: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error in GDrive service: {str(e)}")

@app.post("/permissions/revoke")
async def revoke_drive_permission(request: RevokePermissionRequest):
    print(f"GDrive Service: Request to REVOKE access for {request.user_email} on {request.item_id}")
    drive_service = get_drive_service()
    if not drive_service:
        print("GDrive Service: Drive service not available. Simulating success.")
        return {"status": "simulated_success_due_to_config", "message": f"Simulated: Access revoked for {request.user_email} from item {request.item_id}"}

    try:
        # Find the permission ID for the user and file
        permissions_result = drive_service.permissions().list(fileId=request.item_id, fields="permissions(id,emailAddress)").execute()
        permission_id_to_delete = None
        for p in permissions_result.get('permissions', []):
            if p.get('emailAddress') == request.user_email:
                permission_id_to_delete = p.get('id')
                break
        
        if permission_id_to_delete:
            drive_service.permissions().delete(fileId=request.item_id, permissionId=permission_id_to_delete).execute()
            print(f"GDrive Service: Successfully revoked access for {request.user_email} on {request.item_id}")
            return {"status": "success", "message": f"Access revoked for {request.user_email} from item {request.item_id}"}
        else:
            print(f"GDrive Service: No permission found for {request.user_email} on {request.item_id} to revoke.")
            # Not an error necessarily, could be that access was already revoked or never existed.
            return {"status": "not_found", "message": "Permission not found for user on this item, or already revoked"}
    except HttpError as e:
        print(f"GDrive Service: Google API HttpError revoking permission: {e.status_code} - {e.content}")
        raise HTTPException(status_code=e.status_code, detail=f"Google API Error: {e.content.decode() if isinstance(e.content, bytes) else str(e.content)}")
    except Exception as e:
        print(f"GDrive Service: General error revoking permission: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error in GDrive service: {str(e)}")

@app.get("/items")
async def get_all_gdrive_items():
    now = time.time()
    if _items_cache["data"] is not None and (now - _items_cache["timestamp"] < ITEMS_CACHE_TTL):
        return {"cached": True, "items": _items_cache["data"]}

    drive_service = get_drive_service()
    if not drive_service:
        return {"error": "Google Drive service not available.", "items": []}

    try:
        # List all files/folders the service account can access (first 1000 for now)
        # You can adjust the query to only include folders, or only files, or both
        results = drive_service.files().list(
            pageSize=1000,
            fields="files(id, name, mimeType, parents)"
        ).execute()
        items = [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f["mimeType"],
                "parents": f.get("parents", [])
            }
            for f in results.get("files", [])
        ]
        _items_cache["data"] = items
        _items_cache["timestamp"] = now
        return {"cached": False, "items": items}
    except Exception as e:
        print(f"GDrive Service: Error fetching items: {e}")
        return {"error": str(e), "items": []}

# Example of how you might run this (for development):
# uvicorn microservices.gdrive_service.main:app --reload --port 8002 