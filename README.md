# Trip Planner AI Agent

A FastAPI-powered AI travel planning application that generates practical itineraries, estimated budgets, stay suggestions, travel options, booking links, and policy-aware answers. The project includes a static frontend served by the backend and a policy RAG workflow backed by ChromaDB.

## Features

- AI-generated day-wise trip plans from either structured input or a natural-language prompt.
- Budget estimates by currency, travel mode, stay type, trip length, and number of people.
- Booking helper links for maps, routes, hotels, attractions, food, flights, trains, and buses.
- External travel data endpoints for weather, geocoding, places, hotels, restaurants, flights, and exchange rates.
- Policy document ingestion and question answering using local PDF/TXT files, Hugging Face embeddings, and ChromaDB.
- Static browser frontend available directly from the FastAPI server.

## Tech Stack

- Backend: FastAPI, Uvicorn, Pydantic
- AI model: Groq via LangChain
- External APIs: OpenWeatherMap, Geoapify, ExchangeRate API, AeroDataBox via RapidAPI
- RAG: ChromaDB, Hugging Face embeddings, LangChain document loaders
- Frontend: HTML, CSS, JavaScript

## Project Structure

```text
.
|-- backend/
|   |-- main.py                  # FastAPI app and router registration
|   |-- config.py                # Environment settings
|   |-- trip_agent.py            # LLM prompts, parsing, and response normalization
|   |-- budget_planner.py        # Deterministic budget estimate logic
|   |-- api_clients.py           # External API clients
|   |-- ingest_policies.py       # Policy document ingestion
|   |-- policy_vector_store.py   # Chroma and embeddings setup
|   |-- schemas.py               # Request/response models
|   |-- routers/
|   |   |-- health_router.py
|   |   |-- trip_router.py
|   |   |-- external_api_router.py
|   |   `-- policy_router.py
|   `-- policy_docs/             # PDF/TXT policy documents for RAG
|-- frontend/
|   |-- index.html
|   |-- style.css
|   `-- script.js
|-- chroma_db/                   # Local vector database
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Prerequisites

- Python 3.11 or newer is recommended.
- API keys for the services you want to use:
  - Groq
  - OpenWeatherMap
  - Geoapify
  - ExchangeRate API
  - RapidAPI with AeroDataBox access
  - Hugging Face token for embeddings

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file:

```bash
cp .env.example .env
```

4. Add your real API keys to `.env`.

5. Start the backend:

```bash
uvicorn backend.main:app --reload
```

6. Open the app:

```text
http://127.0.0.1:8000
```

FastAPI documentation is also available at:

```text
http://127.0.0.1:8000/docs
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Groq API key used for itinerary generation and policy answers. |
| `GROQ_MODEL` | No | Groq model name. Defaults to `llama-3.3-70b-versatile`. |
| `RAPIDAPI_KEY` | Yes | RapidAPI key for AeroDataBox flight data. |
| `AERODATABOX_HOST` | No | AeroDataBox RapidAPI host. Defaults to `aerodatabox.p.rapidapi.com`. |
| `WEATHER_API_KEY` | Yes | OpenWeatherMap API key. |
| `EXCHANGE_RATE_API_KEY` | Yes | ExchangeRate API key. |
| `GEOAPIFY_API_KEY` | Yes | Geoapify key for geocoding, places, hotels, and restaurants. |
| `HF_TOKEN` | Yes | Hugging Face token for embedding model access. |
| `HF_EMBEDDING_MODEL` | No | Embedding model. Defaults to `BAAI/bge-large-en-v1.5`. |
| `CHROMA_DB_PATH` | No | Local ChromaDB directory. Defaults to `./chroma_db`. |
| `POLICY_DOCS_PATH` | No | Policy docs directory relative to `backend/` unless absolute. Defaults to `policy_docs`. |
| `POLICY_COLLECTION_NAME` | No | Chroma collection name. Defaults to `travel_policy_docs`. |

## API Overview

Base URL for local development:

```text
http://127.0.0.1:8000
```

### Health

#### `GET /health`

Checks whether the backend is running.

Example:

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok",
  "message": "Backend running successfully"
}
```

## Trip Generation Endpoints

### `POST /trip/generate`

Generates a full itinerary from structured trip details.

Request body:

```json
{
  "source": "Ahmedabad",
  "destination": "Goa",
  "start_date": "2026-06-10",
  "end_date": "2026-06-14",
  "budget": 25000,
  "people": 2,
  "currency": "INR",
  "travel_mode": "flight",
  "stay_type": "budget",
  "interests": ["beaches", "nightlife", "food"]
}
```

Allowed values:

- `travel_mode`: `flight`, `train`, `bus`, `car`, `any`
- `stay_type`: `budget`, `standard`, `luxury`
- Supported budget currencies: `INR`, `USD`, `EUR`, `GBP`, `AED`, `SGD`

Example:

```bash
curl -X POST http://127.0.0.1:8000/trip/generate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "Ahmedabad",
    "destination": "Goa",
    "start_date": "2026-06-10",
    "end_date": "2026-06-14",
    "budget": 25000,
    "people": 2,
    "currency": "INR",
    "travel_mode": "flight",
    "stay_type": "budget",
    "interests": ["beaches", "nightlife", "food"]
  }'
```

Response shape:

```json
{
  "summary": "string",
  "day_wise_plan": [
    {
      "day": 1,
      "title": "string",
      "morning": "string",
      "afternoon": "string",
      "evening": "string",
      "food_suggestion": "string",
      "travel_notes": "string",
      "estimated_cost": 0
    }
  ],
  "estimated_budget": {
    "currency": "INR",
    "travel": 0,
    "stay": 0,
    "food": 0,
    "local_transport": 0,
    "activities": 0,
    "buffer": 0,
    "total": 0,
    "fits_budget": true
  },
  "travel_options": [
    {
      "mode": "string",
      "details": "string",
      "estimated_cost": 0
    }
  ],
  "stay_options": [
    {
      "name": "string",
      "type": "string",
      "location": "string",
      "estimated_price_per_night": 0,
      "note": "string"
    }
  ],
  "tips": ["string"]
}
```

### `POST /trip/parse-prompt`

Converts a natural-language trip request into the structured schema used by `/trip/generate`.

Request body:

```json
{
  "prompt": "Plan a 5 day Goa trip from Ahmedabad for 2 people from June 10 to June 14, budget 25000 INR, flight preferred, budget stay, beaches and food."
}
```

Example response:

```json
{
  "source": "Ahmedabad",
  "destination": "Goa",
  "start_date": "2026-06-10",
  "end_date": "2026-06-14",
  "budget": 25000,
  "people": 2,
  "currency": "INR",
  "travel_mode": "flight",
  "stay_type": "budget",
  "interests": ["beaches", "food"]
}
```

### `POST /trip/generate-from-prompt`

Parses a natural-language prompt and immediately generates the itinerary.

Request body:

```json
{
  "prompt": "Plan a relaxed 4 day Kerala trip from Mumbai for 2 people in August, budget 45000 INR, nature, food, scenic stays."
}
```

Response: same shape as `/trip/generate`.

### `POST /trip/booking-links`

Creates useful booking and discovery links from structured trip details.

Request body: same as `/trip/generate`.

Response shape:

```json
{
  "source": "Ahmedabad",
  "destination": "Goa",
  "date_range": "2026-06-10 to 2026-06-14",
  "links": [
    {
      "label": "Hotel Search",
      "type": "stay",
      "url": "https://www.google.com/travel/hotels/Goa...",
      "note": "Compare hotel options and availability."
    }
  ]
}
```

### `POST /trip/booking-links-from-prompt`

Parses a natural-language prompt and returns booking/discovery links.

Request body:

```json
{
  "prompt": "Plan a 3 day Jaipur trip from Ahmedabad for 4 friends, budget 60000 INR, forts, cafes, local markets, boutique stay."
}
```

Response: same shape as `/trip/booking-links`.

## External API Endpoints

These endpoints proxy external providers and require the matching API keys in `.env`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/external/weather/{city}?days=3` | OpenWeatherMap forecast for a city. `days` is capped to the provider forecast range used by the app. |
| `GET` | `/external/exchange/{base_currency}` | Exchange rates for a base currency. |
| `GET` | `/external/geocode?location=Goa` | Geocode a location with Geoapify. |
| `GET` | `/external/geoapify-places?lat=15.49&lon=73.82&category=tourism.sights&radius=5000&limit=10` | Generic Geoapify places search. |
| `GET` | `/external/places?lat=15.49&lon=73.82&category=tourism.sights&radius=5000&limit=10` | Alias for generic places search. |
| `GET` | `/external/attractions?lat=15.49&lon=73.82&radius=5000&limit=20` | Attractions and museums near coordinates. |
| `GET` | `/external/restaurants?lat=15.49&lon=73.82&radius=5000&limit=20` | Restaurants, cafes, and fast food near coordinates. |
| `GET` | `/external/hotels-nearby?lat=15.49&lon=73.82&radius=10000&limit=20` | Hotels and guest houses near coordinates. |
| `GET` | `/external/places-by-city/{city}?category=tourism.sights&radius=5000&limit=20` | Places search after geocoding the city. |
| `GET` | `/external/place-details?place_id=...&features=details` | Geoapify place details by place ID. |
| `GET` | `/external/place-details?lat=15.49&lon=73.82&features=details` | Geoapify place details by coordinates. |
| `GET` | `/external/flights/{airport_code}` | AeroDataBox flight data for an IATA airport code. |
| `GET` | `/external/hotels/{city}` | Hotel search for a city using Geoapify. |

Example:

```bash
curl "http://127.0.0.1:8000/external/weather/Goa?days=3"
```

## Policy RAG Endpoints

Policy RAG uses files inside `backend/policy_docs/` by default. PDF and TXT files are supported.

### `POST /policy/ingest`

Loads policy documents, splits them into chunks, embeds them, and stores them in ChromaDB.

Example:

```bash
curl -X POST http://127.0.0.1:8000/policy/ingest
```

Example response:

```json
{
  "status": "success",
  "documents_loaded": 42,
  "chunks_created": 120,
  "collection_name": "travel_policy_docs",
  "chroma_path": "./chroma_db"
}
```

### `POST /policy/ask`

Answers policy questions using the ingested documents as context.

Request body:

```json
{
  "question": "What baggage rules should I know before an international connection?"
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/policy/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What baggage rules should I know before an international connection?"}'
```

Response shape:

```json
{
  "question": "What baggage rules should I know before an international connection?",
  "answer": "string",
  "sources": [
    {
      "source": "travel_and_baggage.pdf",
      "page": 1
    }
  ]
}
```

## Frontend Usage

After running the backend, open:

```text
http://127.0.0.1:8000/frontend/index.html
```

The root URL redirects there automatically:

```text
http://127.0.0.1:8000
```

The frontend supports two planning modes:

- Prompt mode: write a natural-language trip request.
- Manual mode: fill source, destination, dates, budget, people, currency, travel mode, stay type, and interests.

It calls these API routes:

- `/trip/generate-from-prompt`
- `/trip/booking-links-from-prompt`
- `/trip/generate`
- `/trip/booking-links`

## Common Development Commands

Run the API:

```bash
uvicorn backend.main:app --reload
```

Run policy ingestion directly:

```bash
python -m backend.ingest_policies
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

## Error Handling Notes

- `401` or `403` from external APIs usually means the matching key in `.env` is missing, invalid, or not enabled for that provider.
- External provider failures are returned as `502` responses by the backend.
- Trip generation can return `413` if the prompt or requested trip context exceeds the current Groq model limit.
- All generated prices and budgets should be treated as estimates unless they come directly from an external live provider.

## Security Notes

- Never commit your real `.env` file.
- Keep API keys private.
- Use `.env.example` as the public template for required configuration.
- The current CORS configuration allows all origins for local development. Restrict `allow_origins` before deploying publicly.
