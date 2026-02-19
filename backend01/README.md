# PharmaGuard Backend

Pharmacogenomics risk analysis engine powered by FastAPI and Google Gemini.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env with your API keys

# 4. Run the server
uvicorn app.main:app --reload

# 5. Open Swagger UI
# http://localhost:8000/docs
```

## Project Structure

```
backend01/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # Environment settings
│   ├── routers/         # API endpoints
│   ├── services/        # Business logic
│   ├── models/          # Pydantic schemas
│   └── data/            # Reference data (star alleles, CPIC)
├── scripts/             # Utility scripts
├── tests/               # Test suite
└── requirements.txt
```

## API Endpoints

| Method | Path       | Description                          |
|--------|-----------|--------------------------------------|
| GET    | /health   | Health check                         |
| POST   | /analyze  | Upload VCF + drugs → risk analysis   |
| GET    | /docs     | Swagger UI                           |
