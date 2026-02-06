# Travel Planner Chatbot

AI-powered travel itinerary planner with constraint-based planning.

## Features

- 💬 **Natural Language Chat**: Describe your trip naturally
- 📋 **Mandatory Form**: 18 structured fields ensure all constraints are captured
- 🤖 **Dual AI Roles**: 
  - **Extractor**: Extracts travel facts from chat
  - **Planner**: Generates constraint-compliant itineraries
- 🔄 **Iterative Refinement**: Request modifications to your itinerary
- 🎨 **Modern UI**: Premium dark theme with glassmorphism

## Architecture

```
User Chat → Flow Controller → Extractor AI → Form Update
                ↓
         Form Complete?
                ↓
           Planner AI → Itinerary → User
                ↑
         Modification Request
```

## Quick Start

### 1. Setup

```bash
cd c:\Users\Admin\travel

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env
```

### 2. Configure LLM

Edit `.env` with your LLM settings:

**For Ollama (local, free):**
```env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=mistral
LLM_API_KEY=ollama
```

**For Mistral AI:**
```env
LLM_PROVIDER=mistral
LLM_API_KEY=your-api-key
LLM_MODEL=mistral-small-latest
```

**For OpenRouter:**
```env
LLM_PROVIDER=openrouter
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=mistralai/mistral-7b-instruct
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session` | POST | Create new session |
| `/api/chat` | POST | Send chat message |
| `/api/form/{id}` | GET | Get form status |
| `/api/itinerary/{id}` | GET | Get current itinerary |

## Form Fields (Hard Constraints)

All 18 fields must be filled before itinerary generation:

- Trip duration (days/nights)
- Number of travelers + group type
- Destinations
- Start/end dates
- Daily activity times
- Weather preference
- Closed days restrictions
- Local guidelines
- Max travel distance per day
- Sightseeing pace
- Cab pickup requirement
- Hotel check-in/out times
- Traffic consideration
- Travel mode

## Testing

```bash
python -m pytest tests/ -v
```

## License

MIT
