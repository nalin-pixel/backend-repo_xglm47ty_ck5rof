Sportex MVP

Overview
- Athlete visibility, team/tournament management, simple performance tracking.
- Built with React + Tailwind (frontend) and FastAPI + MongoDB (backend).
- JWT auth, role-based flows (athlete, coach, organizer, admin).

Quick start
1) Run the stack (installs deps and starts dev servers):
   - Click Run in this environment or execute the provided project-run.
2) Seed sample data (10 athletes, 1 team, 2 events):
   - POST {BACKEND_URL}/seed (use a tool like curl or your browser via a REST client)
3) Open the frontend URL and explore:
   - Landing page
   - Sign in / Create account
   - Athletes search, Event list, Event detail, Dashboard (coach)

Environment
- FRONTEND: Vite + React + Tailwind on port 3000
- BACKEND: FastAPI on port 8000
- DB: MongoDB (DATABASE_URL, DATABASE_NAME are pre-configured in this environment)
- Auth: JWT (HS256), JWT_SECRET (default dev value set, change for production)

Key routes (backend)
- POST /auth/register (email, password, name, role)
- POST /auth/login (OAuth2 form: username=email, password)
- GET /me (requires Authorization: Bearer <token>)
- POST /athletes/me (upsert own profile)
- GET /athletes (search: sport, position, location, min_stat_key, min_stat_value, pagination)
- GET /athletes/{id} (respects privacy)
- POST /teams (coach/organizer)
- POST /teams/{team_id}/add?user_id=
- POST /events (organizer/coach)
- GET /events, GET /events/{id}
- POST /events/{id}/register (athlete registers)
- GET /dashboard/coach (coach view)
- GET /notifications, POST /notifications/{id}/read
- GET /admin/overview, POST /admin/moderate (admin)
- POST /seed (populate sample data)

Frontend screens
- Landing: clean, athletic aesthetic with quick stats and CTAs
- Athlete profile: bio, key stats, achievements, media, simple trend sparkline
- Events: listing + event detail with registration
- Coach dashboard: teams, events, registrations overview

Sample flows
- Create account as Athlete, then update profile from Athletes page in a future iteration.
- Sign in as Organizer (org@sportex.io / org123 after seeding) to create events via API.
- Sign in as Coach (coach@sportex.io / coach123) to view dashboard.

OpenAPI / Postman
- OpenAPI JSON available at {BACKEND_URL}/openapi.json
- Import into Postman directly.

Security & privacy (MVP)
- Password hashing with bcrypt via passlib
- JWT sessions, role checks on protected routes
- Profile privacy setting (public/limited/private)
- Basic validation via Pydantic models
- GDPR-style deletion can be added as /me/delete in next iteration

Testing
- Backend unit tests using FastAPI TestClient: backend/tests/test_core.py
- Run: pytest (from backend dir) if pytest is available in this environment

Deployment (suggested)
- Frontend: Vercel/Netlify (configure VITE_BACKEND_URL)
- Backend: Render/Heroku/Fly.io (set DATABASE_URL, DATABASE_NAME, JWT_SECRET)

Notes
- Media uploads are placeholders (URLs). S3 integration can be added next.
- Google Maps & analytics placeholders; add as needed.
- CSV export endpoints are not included in MVP but straightforward to add from existing data.
