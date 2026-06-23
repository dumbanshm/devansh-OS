# ── Stage 1: build the Tailwind stylesheet ─────────────────────────────────
FROM node:20-alpine AS css
WORKDIR /build
COPY package.json tailwind.config.js ./
COPY web/src ./web/src
COPY web/index.html ./web/index.html
COPY web/static/js ./web/static/js
RUN npx --yes tailwindcss@3.4.17 -c tailwind.config.js \
        -i web/src/input.css -o web/static/app.css --minify

# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY web ./web
COPY --from=css /build/web/static/app.css ./web/static/app.css

# SQLite lives in a mounted volume so data survives container rebuilds.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python", "-m", "app.main"]
