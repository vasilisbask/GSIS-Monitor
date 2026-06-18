# 1. Backend Service Stage
FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 2. Pinger Daemon Stage
FROM golang:1.22-alpine AS pinger-builder
WORKDIR /build
COPY pinger/go.mod pinger/go.sum ./
RUN go mod download
COPY pinger/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o pinger-bin .

FROM alpine:latest AS pinger
RUN apk --no-cache add ca-certificates
WORKDIR /app
COPY --from=pinger-builder /build/pinger-bin ./pinger
CMD ["./pinger"]

# 3. Frontend Web Service Stage
FROM node:26-alpine AS frontend
WORKDIR /app
COPY frontend/package.json ./
COPY frontend/build ./build
COPY frontend/node_modules ./node_modules
EXPOSE 3000
ENV PORT=3000
CMD ["node", "build"]
