# Docker Deployment Guide

This directory contains Docker configuration files for deploying the Pooling Calculator as a containerized web application.

## Prerequisites

- Docker Desktop installed and running
- At least 2GB of available disk space

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# From the project root directory
cd docker
docker-compose up -d
```

The application will be available at http://localhost:7860

To stop the application:
```bash
docker-compose down
```

### Option 2: Using Docker Directly

```bash
# Build the image
docker build -f docker/Dockerfile -t pooling-calculator .

# Run the container
docker run -d -p 7860:7860 --name pooling-calculator pooling-calculator
```

To stop the container:
```bash
docker stop pooling-calculator
docker rm pooling-calculator
```

## Configuration

### Environment Variables

The following environment variables can be configured:

- `GRADIO_SERVER_NAME`: Server bind address (default: `0.0.0.0` in Docker, `127.0.0.1` locally)
- `GRADIO_SERVER_PORT`: Server port (default: `7860`)
- `PYTHONUNBUFFERED`: Python output buffering (default: `1` for real-time logs)

### Custom Port

To run on a different port, modify the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "8080:7860"  # Access at http://localhost:8080
```

Or with direct Docker:
```bash
docker run -d -p 8080:7860 --name pooling-calculator pooling-calculator
```

## Deployment to Server

### 1. Copy Files to Server

```bash
# Package the application
tar -czf pooling-calculator.tar.gz \
  docker/ \
  src/ \
  pyproject.toml \
  uv.lock

# Transfer to server (example with scp)
scp pooling-calculator.tar.gz user@server:/path/to/deploy/
```

### 2. Deploy on Server

```bash
# On the server
cd /path/to/deploy
tar -xzf pooling-calculator.tar.gz

# Start the application
cd docker
docker-compose up -d
```

### 3. Verify Deployment

```bash
# Check container status
docker ps

# View logs
docker-compose logs -f pooling-calculator

# Test health
curl http://localhost:7860
```

## Troubleshooting

### Container fails to start

Check logs:
```bash
docker-compose logs pooling-calculator
```

### Port already in use

Change the port mapping in `docker-compose.yml` or stop the conflicting service.

### Permission denied errors

Ensure Docker Desktop is running and you have permission to run Docker commands.

### Build fails

1. Ensure `uv.lock` is up to date:
   ```bash
   uv lock
   ```

2. Check Docker has enough disk space:
   ```bash
   docker system df
   ```

3. Clean Docker cache if needed:
   ```bash
   docker system prune
   ```

## Updating the Application

```bash
# Pull latest code
git pull

# Rebuild and restart
cd docker
docker-compose down
docker-compose up -d --build
```

## Production Considerations

### Security

- Run behind a reverse proxy (nginx, Caddy) with HTTPS
- Implement authentication if needed
- Restrict network access with firewall rules

### Resource Limits

Add resource constraints in `docker-compose.yml`:

```yaml
services:
  pooling-calculator:
    # ... other config ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Logging

Configure logging driver in `docker-compose.yml`:

```yaml
services:
  pooling-calculator:
    # ... other config ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Persistence

To persist temporary files (downloads), add a volume:

```yaml
services:
  pooling-calculator:
    # ... other config ...
    volumes:
      - pooling-data:/tmp

volumes:
  pooling-data:
```

## Architecture

The Docker image uses a multi-stage build for optimization:

1. **Builder stage**: Installs dependencies using `uv`
2. **Runtime stage**: Copies only necessary files and virtual environment

This approach minimizes image size while maintaining reproducibility.

## Support

For issues or questions:
- Check application logs: `docker-compose logs -f`
- Review Docker documentation: https://docs.docker.com/
- Report issues at: [GitHub repository URL]
