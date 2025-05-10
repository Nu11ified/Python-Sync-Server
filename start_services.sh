   #!/bin/bash
   echo "Starting all services..."

   # Activate virtual environment (adjust path if your venv is elsewhere)
   source .venv/bin/activate # Or the specific name you used, e.g., .jrp-server-venv/bin/activate

   uvicorn orchestrator.main:app --reload --port 8000 &
   UVICORN_PID_ORCHESTRATOR=$!
   echo "Orchestrator service started with PID $UVICORN_PID_ORCHESTRATOR"

   uvicorn microservices.discord_service.main:app --reload --port 8001 &
   UVICORN_PID_DISCORD=$!
   echo "Discord service started with PID $UVICORN_PID_DISCORD"

   uvicorn microservices.gdrive_service.main:app --reload --port 8002 &
   UVICORN_PID_GDRIVE=$!
   echo "GDrive service started with PID $UVICORN_PID_GDRIVE"

   uvicorn microservices.teamspeak_service.main:app --reload --port 8003 &
   UVICORN_PID_TEAMSPEAK=$!
   echo "Teamspeak service started with PID $UVICORN_PID_TEAMSPEAK"

   echo "All services launched. Use 'kill <PID>' or 'pkill -f uvicorn' to stop them."
   # Or a function to kill them all:
   # trap "kill $UVICORN_PID_ORCHESTRATOR $UVICORN_PID_DISCORD $UVICORN_PID_GDRIVE $UVICORN_PID_TEAMSPEAK; exit" INT TERM EXIT