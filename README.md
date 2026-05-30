# RoadAid AI Assistant

An AI-powered assistant that lets you query your **RoadAid MongoDB database** using plain English, built with:

- **Gemini 2.5 Pro** — LLM for query generation and answer summarisation
- **LangChain** — prompt templates and chain orchestration
- **MongoDB** — the primary data store
- **ChromaDB** — vector store for RAG over uploaded PDF documents
- **FastAPI** — REST API layer

---

## Project Structure

```
roadaid-chatbot/
│
├── app/
│   ├── main.py                  # FastAPI app entry point
│   │
│   ├── database/
│   │   └── mongo_client.py      # MongoDB connection (async + sync)
│   │
│   ├── schemas/                 # Pydantic models for each collection
│   │   ├── users.py
│   │   ├── roads.py
│   │   ├── accidents.py
│   │   ├── dailyprogresses.py
│   │   ├── drivers.py
│   │   ├── dprs.py
│   │   ├── fuels.py
│   │   └── employees.py
│   │
│   ├── prompts/
│   │   └── mongo_prompts.py     # LangChain prompt templates
│   │
│   ├── services/
│   │   ├── query_service.py     # Query generation + execution
│   │   └── chat_service.py      # Full chat pipeline orchestrator
│   │
│   ├── rag/
│   │   ├── loader.py            # PDF loader + text splitter
│   │   ├── embeddings.py        # Google Generative AI embeddings
│   │   └── retriever.py         # ChromaDB store + RAG answer
│   │
│   ├── routes/
│   │   ├── chat.py              # POST /api/v1/chat
│   │   └── rag.py               # POST /api/v1/rag/upload + /rag/query
│   │
│   └── utils/
│       └── query_validator.py   # Read-only query safety validator
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prerequisites

- Python 3.11+
- MongoDB running locally or a MongoDB Atlas connection string
- A **Google AI Studio API key** for Gemini 2.5 Pro

---

## Setup

### 1. Clone and create a virtual environment

```bash
cd roadaid-chatbot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=roadaid

GOOGLE_API_KEY=your-google-api-key-here
GEMINI_MODEL=gemini-2.5-pro
GEMINI_EMBEDDING_MODEL=models/embedding-001

CHROMA_PERSIST_DIR=./chroma_db
```

> Get your Google API key at https://aistudio.google.com/app/apikey

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`.

---

## API Reference

### Health Check

```
GET /health
```

```json
{ "status": "ok", "service": "RoadAid AI Assistant", "llm": "gemini-2.5-pro" }
```

---

### POST /api/v1/chat

Ask any natural language question about the RoadAid database.

**Request:**
```json
{
  "question": "How many accidents happened this month?"
}
```

**Response:**
```json
{
  "answer": "There were 7 accidents recorded this month across all roads.",
  "query": {
    "collection": "accidents",
    "operation": "count",
    "filter": { "date": { "$gte": "2026-05-01T00:00:00Z" } }
  },
  "data": [{ "count": 7 }]
}
```

---

### POST /api/v1/rag/upload

Upload a PDF document to be indexed for RAG queries.

```bash
curl -X POST http://localhost:8000/api/v1/rag/upload \
  -F "file=@roadwork_report.pdf"
```

**Response:**
```json
{
  "message": "Document uploaded and indexed successfully.",
  "filename": "roadwork_report.pdf",
  "chunks_added": 42
}
```

---

### POST /api/v1/rag/query

Ask a question answered from uploaded PDF documents.

**Request:**
```json
{
  "question": "What are the safety guidelines for road workers?"
}
```

**Response:**
```json
{
  "answer": "According to the uploaded documents, road workers must wear...",
  "source_documents": [
    { "source": "uploaded_docs/roadwork_report.pdf", "page": 3 }
  ]
}
```

---

## Example Questions

| Question | Collection queried |
|---|---|
| `Show all active drivers` | `drivers` |
| `How many accidents happened this month?` | `accidents` |
| `List roads under maintenance` | `roads` |
| `Show fuel expenses this week` | `fuels` |
| `Which employee manages NH44?` | `employees` |
| `Show DPR reports for today` | `dprs` |
| `What work was completed on NH44 today?` | `dailyprogresses` |

---

## How It Works

```
User Question
     │
     ▼
LangChain Prompt (schema-aware)
     │
     ▼
Gemini 2.5 Pro generates MongoDB query dict
     │
     ▼
Query Validator (blocks destructive operations)
     │
     ▼
PyMongo executes read query against MongoDB
     │
     ▼
Raw results sent back to Gemini 2.5 Pro
     │
     ▼
Human-readable answer returned via FastAPI
```

---

## Interactive Docs

Once the server is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc:       `http://localhost:8000/redoc`

---

## Future Improvements

- LangGraph for multi-step reasoning
- Conversation memory / chat history
- Authentication (JWT)
- Analytics dashboard
- Advanced RAG with re-ranking
- Multi-agent workflows
