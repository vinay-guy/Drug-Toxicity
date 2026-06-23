# Docker deployment (recommended for RDKit)

This guide shows how to build and run the ToxPredict app in Docker. Using Docker ensures a reproducible environment and allows installing RDKit via conda-forge.

Build the image

```bash
# From repository root
docker build -t toxpredict:latest .
```

Run locally

```bash
# Run with mounts for models/data (so you can update them on host)
docker run -it --rm -p 8501:8501 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/data:/app/data \
  -e PYTHONPATH=src \
  toxpredict:latest
```

Start with docker-compose

```bash
docker-compose up --build -d
```

Setting credentials

- Do NOT embed secrets in `docker-compose.yml`.
- To pass the login, either mount `models/.auth.json` into the container or set environment variables at runtime:

```bash
# Example: set env vars when running
docker run -p 8501:8501 -e LOGIN_USERNAME=admin -e LOGIN_PASSWORD_HASH='<salthex:hashhex>' toxpredict:latest
```

Notes

- The Docker image creates a Conda env named `toxpredict` with Python 3.10 and installs `rdkit` from conda-forge.
- The image may be large due to Conda/RDKit packages.
- For production, consider pushing the image to a registry (Docker Hub, ECR, ACR) and running on a managed container service.
