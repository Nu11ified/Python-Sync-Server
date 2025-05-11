FROM python:3.12-slim

# Install system dependencies (add more if needed for your services)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables (override in docker-compose as needed)
ENV PYTHONUNBUFFERED=1

# Default command (override in docker-compose)
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"] 