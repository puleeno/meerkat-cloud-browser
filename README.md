# Browser Control API

A browser automation system using Rust and Python with Firefox WebDriver.

## Architecture

- Python FastAPI backend for browser control
- Rust proxy server for request handling
- Firefox browser automation using geckordp

## Setup

### Prerequisites

- Docker and Docker Compose
- Firefox browser (for local development)

### Running with Docker

```bash
docker-compose up -d
```

### Running Locally

1. Start Python API:

```bash
cd python_api
pip install -r requirements.txt
hypercorn python_api/app/main:app --bind 0.0.0.0:8000
```

2. Start Rust Proxy:

```bash
cd rust_proxy
cargo run
```

## API Endpoints
- `POST /browser/start` - Start browser
- `POST /browser/navigate` - Navigate to URL
- `POST /browser/stop` - Stop browser
- `GET /browser/screenshot` - Take screenshot
- `POST /browser/execute` - Execute JavaScript

## Development

- Python API documentation: http://localhost:8000/docs
- Logs are stored in `./logs` directory
