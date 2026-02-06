# FastAPI Multi-Agent System

Backend service built with FastAPI that supports LangGraph multi-agent workflows and integrates with a .NET API.

## 🚀 Features

- **FastAPI Framework**: Modern, fast (high-performance) web framework for building APIs
- **LangGraph Support**: Prepared structure for multi-agent AI workflows (future implementation)
- **.NET Integration**: Bidirectional communication with .NET backend services
- **Type-Safe Configuration**: Pydantic-based settings management
- **CORS Enabled**: Ready for frontend integration
- **Auto-Generated Docs**: Interactive API documentation at `/docs`

## 📋 Prerequisites

- Python 3.9 or higher
- .NET API running (optional for basic testing)

## 🛠️ Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**

```bash
.\venv\Scripts\activate
```

**Linux/Mac:**

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

- `DOTNET_API_URL`: URL of your .NET API
- `GOOGLE_API_KEY`: Google API key for Gemini (for future agent features)
- `HOST` and `PORT`: Server configuration

## 🏃 Running the Application

### Development Mode (with auto-reload)

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Or simply:

```bash
python -m uvicorn src.main:app --reload
```

The API will be available at:

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 API Endpoints

### Health Checks

- `GET /health` - Basic health check
- `GET /health/dotnet` - Check .NET API connectivity

### Test Endpoints (for development)

- `POST /api/test/echo` - Echo back received data (test .NET → Python)
- `GET /api/test/call-dotnet` - Test calling .NET API (test Python → .NET)
- `POST /api/test/call-dotnet-custom` - Call custom .NET endpoint
- `POST /api/test/process` - Process data with optional .NET interaction

## 🧪 Testing Communication

### Test 1: Python is Running

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "message": "FastAPI service is running",
  "timestamp": "2024-02-04T...",
  "details": {
    "service": "fastapi-multi-agent",
    "version": "1.0.0"
  }
}
```

### Test 2: .NET API Connectivity

```bash
curl http://localhost:8000/health/dotnet
```

### Test 3: Echo Endpoint (.NET calls Python)

```bash
curl -X POST http://localhost:8000/api/test/echo \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello from .NET\", \"data\": {\"test\": true}}"
```

### Test 4: Python calls .NET

```bash
curl http://localhost:8000/api/test/call-dotnet
```

### Test 5: Custom .NET Endpoint Call

```bash
curl -X POST http://localhost:8000/api/test/call-dotnet-custom \
  -H "Content-Type: application/json" \
  -d "{\"endpoint\": \"/api/your-endpoint\", \"method\": \"GET\"}"
```

## 🏗️ Project Structure

```
fastapi/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── api/
│   │   ├── __init__.py        # API router setup
│   │   └── routes/
│   │       ├── health.py      # Health check endpoints
│   │       └── test.py        # Test endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   └── dotnet_client.py   # .NET API client
│   └── agents/
│       └── __init__.py        # Future LangGraph agents
├── venv/                      # Virtual environment
├── .env                       # Environment variables (create from .env.example)
├── .env.example              # Example environment configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 🔄 .NET Integration

### From .NET to Python

Your .NET application can call Python endpoints:

```csharp
using System.Net.Http;
using System.Text;
using System.Text.Json;

var client = new HttpClient();
var content = new StringContent(
    JsonSerializer.Serialize(new { message = "Hello from .NET", data = new { test = true } }),
    Encoding.UTF8,
    "application/json"
);

var response = await client.PostAsync("http://localhost:8000/api/test/echo", content);
var result = await response.Content.ReadAsStringAsync();
```

### From Python to .NET

The Python service can call your .NET API:

```python
from src.services.dotnet_client import dotnet_client

# GET request
result = await dotnet_client.get("/api/your-endpoint")

# POST request
result = await dotnet_client.post("/api/your-endpoint", data={"key": "value"})
```

## 🤖 Future: LangGraph Multi-Agent System

The `src/agents/` directory is prepared for future implementation of:

- **Planner Agent**: Route planning and itinerary creation
- **Coordinator Agent**: Workflow orchestration
- **Integration Agent**: Enhanced .NET API communication
- **Response Agent**: Formatting and structuring responses

This will be implemented using LangGraph for complex multi-agent workflows.

## 🐛 Troubleshooting

### .NET API Connection Issues

If you get errors connecting to .NET:

1. Ensure .NET API is running on the configured URL
2. Check CORS settings on both sides
3. For HTTPS with self-signed certificates, the client disables SSL verification (development only)

### Import Errors

Make sure you're in the project root directory and virtual environment is activated:

```bash
# Check current directory
pwd  # Should show .../fastapi

# Activate venv if not already
.\venv\Scripts\activate  # Windows
```

### Port Already in Use

If port 8000 is already in use:

```bash
uvicorn src.main:app --reload --port 8001
```

## 📝 Notes

- This is a development setup with SSL verification disabled for localhost testing
- CORS is configured to allow requests from common development URLs
- All test endpoints are meant for development and should be secured/removed in production
- The LangGraph agent structure is prepared but not yet implemented

## 📞 Support

For issues or questions, please refer to the project documentation or contact the development team.
