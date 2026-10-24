# WindTrace

WindTrace measures how accurate GB day-ahead wind forecasts were, comparing each half-hour of January 2026 with the forecast available at gate closure.

## Features

- Live Elexon FUELHH and WINDFOR data, refreshable from the dashboard.
- Actual-versus-forecast comparison for every settlement period.
- MAE, RMSE, bias, MAPE, sMAPE and WAPE, with daily, hourly and lead-time breakdowns.
- Forecast history showing every vintage and the one selected at the cutoff.
- Responsive React dashboard with light and dark themes.

## Technology

React, TypeScript, Vite and Tailwind CSS on the frontend; FastAPI, Python and pandas on the backend; Docker for local containers.

## Project Structure

```text
lkcf/
├── backend/          # FastAPI backend and data processing (FastAPI, Python, pandas, Elexon API)
├── frontend/         # React dashboard and UI components (React, TypeScript, Vite, Tailwind CSS)
├── docker-compose.yml # Local Docker configuration
├── .gitignore        # Files excluded from Git
└── README.md         # Project documentation

## Data and methodology

- **FUELHH** (`fuelType=WIND`) provides half-hourly actual wind generation.
- **WINDFOR** provides hourly wind forecast publications.

For each delivery period, WindTrace uses the latest WINDFOR publication at or before 09:20 Europe/London on the previous day. This cutoff is a pilot assumption, not an official Elexon rule. Each hourly forecast is applied to both half-hours in its hour. Periods without an eligible forecast or actual generation are excluded from the metrics.

## Setup

Prerequisites: Python 3.11+ and Node 20+.

Create the local environment files:

```bash
cp backend/.env.example backend/.env && cp frontend/.env.example frontend/.env
```

Edit `backend/.env` for backend settings (`DATA_SOURCE`, `ELEXON_BASE_URL`, `LIVE_CACHE_TTL_SECONDS`, `ALLOWED_ORIGINS`). Edit `frontend/.env` to set `VITE_API_BASE_URL` to the backend URL.

### Backend

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: http://localhost:5173.

## Docker

```bash
docker compose up --build
```

Dashboard: http://localhost:3000. API docs: http://localhost:8000/docs.

## Links

- Frontend: `https://lkcf.vercel.app/`
- Backend: `https://lkcf.onrender.com/`
- Repository: `https://github.com/kobruhhhhh/lkcf`

### AI Disclosure
AI tools were used only for implementation assistance and code cleanup. The application logic, data processing, and reported forecast accuracy results are based on the project implementation and Elexon BMRS API data. Synthetic records are used only in clearly labelled tests.