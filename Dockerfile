# The on-demand scanner needs both Python (Flask) and Node (Playwright/axe-core), which
# Render's plain "python" or "node" runtimes don't give you together, so this builds a
# single image with both.
FROM node:20-bookworm-slim

# System Python, plus the OS libraries Chromium needs to run headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node dependencies and the Chromium browser (with its own OS-level dependencies) first,
# so this layer is reused on every rebuild unless package.json actually changes.
COPY package.json package-lock.json ./
RUN npm ci \
    && npx playwright install --with-deps chromium

# Python dependencies in a virtualenv (Debian's system Python refuses a plain pip install).
COPY requirements.txt ./
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt gunicorn
ENV PATH="/venv/bin:$PATH"

COPY . .

ENV PORT=5020
EXPOSE 5020

CMD gunicorn --chdir src app:app --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT
