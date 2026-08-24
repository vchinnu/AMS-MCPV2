# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "uvicorn[standard]>=0.29"

# Copy server source — do NOT copy .env (secrets come from ACA env vars at runtime)
COPY config.py           .
COPY la_client.py        .
COPY schema_registry.py  .
COPY schemas/            ./schemas/
COPY domain_knowledge.py .
COPY domain_knowledge_ha.py .
COPY domain_knowledge_os.py .
COPY domain_registry.py  .
COPY server.py           .
COPY run_server.py       .
COPY tools/              ./tools/

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8000

# run_server.py uses FastMCP streamable-http transport (MCP 1.x standard)
CMD ["python", "run_server.py"]
