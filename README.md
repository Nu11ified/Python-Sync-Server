# JRP Server - Python Backend Services

This project contains the Python backend services for the JRP internal tool, including an orchestrator and microservices for Discord, Google Drive, and Teamspeak integration.

## Project Structure

```
jrp-server/
├── .env.example         # Example environment variables
├── .env                 # Local environment variables (ignored by git)
├── requirements.txt     # Root Python dependencies
├── start_services.sh    # Script to start all Python services (example)
├── orchestrator/        # Main orchestrator service (FastAPI)
│   └── main.py
├── microservices/       # Individual microservices (FastAPI)
│   ├── discord_service/
│   │   └── main.py      # Includes Discord bot logic
│   ├── gdrive_service/
│   │   └── main.py
│   └── teamspeak_service/
│       └── main.py
└── common/              # (Currently unused, for shared utilities if needed)
    └── README.md
```

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd jrp-server
    ```

2.  **Create and Activate Virtual Environment (using `uv`):**
    ```bash
    uv venv .venv # or your preferred venv name
    source .venv/bin/activate
    ```
    (For Windows, use `.venv\Scripts\activate`)

3.  **Install Dependencies:**
    ```bash
    uv pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    *   Copy `.env.example` to a new file named `.env`:
        ```bash
        cp .env.example .env
        ```
    *   **Edit `.env` and fill in all required values.** This is crucial for the services to run correctly. See the `.env.example` section below for details on each variable.
    *   **Important:** Add `.env` to your `.gitignore` file if it's not already there to prevent committing secrets.

## Environment Variables (`.env.example`)

The `.env.example` file (and your `.env` file) should contain the following variables:

```env
# Orchestrator Configuration
NEXTJS_SERVER_BASE_URL="http://localhost:3000/api/internal" # Base URL for your Next.js internal API
DISCORD_SERVICE_URL="http://localhost:8001"
GDRIVE_SERVICE_URL="http://localhost:8002"
TEAMSPEAK_SERVICE_URL="http://localhost:8003"

# Discord Service Configuration
DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE" # Token for your Discord Bot Application
# ORCHESTRATOR_URL is used by discord_service for hooks, defaults to http://localhost:8000 if not set directly in discord_service/main.py

# GDrive Service Configuration
# Path to your Google Cloud service account JSON key file.
# This service account needs access to the Drive items it will manage.
GOOGLE_APPLICATION_CREDENTIALS="path/to/your/google_service_account.json"

# Teamspeak Service Configuration
TS_SERVER_HOST="your_teamspeak_server_ip_or_hostname"
TS_SERVER_QUERY_PORT="10011" # Default ServerQuery port
TS_VIRTUAL_SERVER_ID="1"     # ID of the virtual server to manage
TS_QUERY_LOGIN_NAME="serveradmin_or_your_query_user"
TS_QUERY_LOGIN_PASSWORD="YOUR_TS_QUERY_PASSWORD_HERE" # Password for the ServerQuery user
```

**Key Credentials to Obtain:**
*   `DISCORD_BOT_TOKEN`: From the Discord Developer Portal for your bot application. Ensure "Server Members Intent" and "Message Content Intent" are enabled for the bot.
*   `GOOGLE_APPLICATION_CREDENTIALS`: Path to the JSON key for a Google Cloud Service Account. This service account must be granted appropriate permissions on the Google Drive files/folders it will manage.
*   `TS_QUERY_LOGIN_PASSWORD`: The password for your Teamspeak ServerQuery user. This user needs permissions to manage server groups and find clients. Also, whitelist the IP of the machine running `teamspeak_service` in your Teamspeak server's `query_ip_whitelist.txt`.

## Running the Services

### Individually

You can run each service in a separate terminal. Ensure your virtual environment is activated. Navigate to the project root (`jrp-server/`).

*   **Orchestrator:**
    ```bash
    uvicorn orchestrator.main:app --reload --port 8000
    ```
*   **Discord Service:** (Requires `DISCORD_BOT_TOKEN`)
    ```bash
    uvicorn microservices.discord_service.main:app --reload --port 8001
    ```
*   **Google Drive Service:** (Requires `GOOGLE_APPLICATION_CREDENTIALS`)
    ```bash
    uvicorn microservices.gdrive_service.main:app --reload --port 8002
    ```
*   **Teamspeak Service:** (Requires Teamspeak env vars, especially `TS_QUERY_LOGIN_PASSWORD`)
    ```bash
    uvicorn microservices.teamspeak_service.main:app --reload --port 8003
    ```

### All at Once (using `start_services.sh`)

An example `start_services.sh` script is provided (or you can create one) to launch all services.
```bash
# Example start_services.sh content:
# #!/bin/bash
# echo "Starting all services..."
# source .venv/bin/activate # Adjust if your venv name is different
# uvicorn orchestrator.main:app --reload --port 8000 &
# uvicorn microservices.discord_service.main:app --reload --port 8001 &
# uvicorn microservices.gdrive_service.main:app --reload --port 8002 &
# uvicorn microservices.teamspeak_service.main:app --reload --port 8003 &
# echo "All services launched. Use pkill -f uvicorn to stop them all."

chmod +x start_services.sh
./start_services.sh
```
To stop them, you can use `pkill -f uvicorn` (this will kill all uvicorn processes running under your user).

## Next.js API Interaction (Python Orchestrator Expectations)

The Python orchestrator service (`orchestrator/main.py`) expects to interact with a Next.js backend API for user data and mappings. The base URL for this API is configured via the `NEXTJS_SERVER_BASE_URL` environment variable.

Key interactions (currently mocked in the orchestrator, to be implemented in Next.js):

1.  **Fetch User Linked Accounts & Internal ID:**
    *   **Purpose:** Get user's internal ID, linked Google email, Teamspeak UID, and linkage status.
    *   **Orchestrator Expectation (Example):** `GET {NEXTJS_SERVER_BASE_URL}/user/details/{discord_id}`
    *   **Expected Next.js Response (Example):**
        ```json
        {
            "discord_id": "string",
            "internal_user_id": "string_or_null", // Primary user key in Next.js DB
            "google_email": "string_or_null",
            "teamspeak_unique_id": "string_or_null",
            "is_google_linked": false,
            "is_teamspeak_linked": false
        }
        ```

2.  **Fetch Role Mappings:**
    *   **Purpose:** Get admin-defined mappings between Discord roles and GDrive/Teamspeak permissions.
    *   **Orchestrator Expectation (Example):** `GET {NEXTJS_SERVER_BASE_URL}/mappings?guild_id={guild_id}`
    *   **Expected Next.js Response (Example):**
        ```json
        {
            "mappings": [
                {
                    "mapping_id": "uuid",
                    "discord_role_id": "string",
                    "discord_role_name": "string",
                    "guild_id": "string",
                    "google_drive_permissions": [
                        {"item_id": "string", "item_name": "string", "access_level": "reader|writer|commenter"}
                    ],
                    "teamspeak_groups": [
                        {"group_id": "string", "group_name": "string"}
                    ]
                }
            ]
        }
        ```

3.  **Fetch User's Previous Discord Roles (for a specific guild):**
    *   **Purpose:** To compare with current roles and determine additions/removals.
    *   **Orchestrator Expectation (Example):** `GET {NEXTJS_SERVER_BASE_URL}/user/{internal_user_id}/discord/roles?guild_id={guild_id}`
    *   **Expected Next.js Response (Example):**
        ```json
        {
            "roles": [
                {"id": "string", "name": "string"}
            ]
        }
        ```

4.  **Update User's Discord Roles (for a specific guild):**
    *   **Purpose:** Store the latest known Discord roles for a user.
    *   **Orchestrator Expectation (Example):** `POST {NEXTJS_SERVER_BASE_URL}/user/{internal_user_id}/discord/roles`
    *   **Orchestrator Request Body (Example):**
        ```json
        {
            "guild_id": "string",
            "roles": [
                {"id": "string", "name": "string"}
            ]
        }
        ```

**Note:** The exact routes and payload structures for the Next.js API should be finalized in coordination with the Next.js development. The above are examples of what the Python orchestrator is currently designed to expect.

## Development Notes
*   The `discord_service` runs a live Discord bot. It needs its token and for the bot to be in a server to detect role changes.
*   `gdrive_service` and `teamspeak_service` will attempt real API calls if their respective credentials are correctly configured in `.env`. They have fallbacks to simulated success if credentials/libraries are missing, to allow testing of the orchestrator flow.
*   Error handling in the orchestrator for calls to microservices has been improved, but further resilience (e.g., retries, dead-letter queues for critical updates) could be added for a production system.

## Microservice Endpoints for Admin Mapping Menus

Each microservice provides an endpoint to list all possible mapping targets (with in-memory caching):

### Discord Service
- **Endpoint:** `GET /roles`
- **Description:** Returns all roles (excluding @everyone) for all guilds the bot is in.
- **Cache:** 5 minutes (in-memory)
- **Example Response:**
    ```json
    {
      "cached": false,
      "roles": [
        {"id": "1234567890", "name": "Member", "guild_id": "987654321", "guild_name": "My Server"},
        {"id": "2345678901", "name": "Moderator", "guild_id": "987654321", "guild_name": "My Server"}
      ]
    }
    ```

### Teamspeak Service
- **Endpoint:** `GET /groups`
- **Description:** Returns all server groups for the configured virtual server.
- **Cache:** 5 minutes (in-memory)
- **Example Response:**
    ```json
    {
      "cached": false,
      "groups": [
        {"id": "6", "name": "Server Admin"},
        {"id": "7", "name": "Normal"}
      ]
    }
    ```

### Google Drive Service
- **Endpoint:** `GET /items`
- **Description:** Returns all files/folders the service account can access (first 1000).
- **Cache:** 10 minutes (in-memory)
- **Example Response:**
    ```json
    {
      "cached": false,
      "items": [
        {"id": "1a2b3c", "name": "Project Docs", "type": "application/vnd.google-apps.folder", "parents": []},
        {"id": "4d5e6f", "name": "Meeting Notes.docx", "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "parents": ["1a2b3c"]}
      ]
    }
    ```

These endpoints are intended for use by the admin panel to populate mapping menus, and are cached to avoid excessive API calls. The cache TTLs can be adjusted as needed in each microservice.
