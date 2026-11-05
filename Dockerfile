FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /build/frontend/dist ./frontend/dist/
RUN mkdir -p /app/data /var/data && chown -R 10001:10001 /app/data /var/data
EXPOSE 8000
CMD ["python", "-m", "backend.serve"]
