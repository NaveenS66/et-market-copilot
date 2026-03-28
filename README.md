# ET Investor Copilot

Portfolio-aware signal intelligence agent for Indian retail investors. ET AI Hackathon 2026 — Track 6.

## Setup

### Backend
```bash
cd backend
pip install -e .
cp .env.example .env
# Fill in your API keys in .env
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Architecture
See `.kiro/specs/et-investor-copilot/design.md`
