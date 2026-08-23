FROM node:20-alpine AS frontend
WORKDIR /ui
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ ./
COPY VERSION ./VERSION
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY web/backend/requirements.txt /app/web/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/web/backend/requirements.txt
COPY VERSION /app/VERSION
COPY core /app/core
COPY web /app/web
COPY --from=frontend /ui/dist /app/web/frontend/dist
ENV PYTHONPATH=/app
ENV EFFICIENCYFINDER_DATA=/data
EXPOSE 4322
CMD ["uvicorn", "web.backend.app:app", "--host", "0.0.0.0", "--port", "4322", "--timeout-keep-alive", "30"]
