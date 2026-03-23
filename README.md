# Draught Backend (draught-be)

Django backend for the Draught board game with JWT auth, WebSocket multiplayer, AI opponent, matchmaking, and ELO ratings.

## Structure

```
draught-be/
├── config/           # Django project config (settings, asgi, urls)
├── apps/
│   ├── users/        # Custom User (rating, games_played, games_won)
│   ├── authentication/  # JWT (register, login)
│   ├── games/        # Game & Move models, REST API, WebSocket consumer
│   ├── board_engine/ # Core game logic (10x10, moves, captures, kings)
│   ├── matchmaking/  # Redis queues (ranked/casual)
│   ├── ratings/      # ELO calculation
│   └── ai/           # Easy, Medium, Hard AI
├── manage.py
└── requirements.txt
```

## Setup

```bash
python -m venv venv
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env      # optional
python manage.py migrate
```

## Admin

Django admin: **http://localhost:8000/admin/** (title: **Draught Admin**).

**If you don’t see any models or can’t log in:** the project uses a custom User model (`users.User`). A superuser created before this setup (or in another database) won’t exist in the current DB. Create one that does:

```bash
python manage.py createsuperuser
```

Or ensure at least one superuser exists (prompts only if none exist):

```bash
python manage.py ensure_admin
```

Log in with that user. You should see:

| App | Models |
|-----|--------|
| **Users** | Users (rating, stats, staff flags) |
| **Games** | Games, Moves, Game challenges, Game chat messages |

If the dashboard is empty, your user may not be staff — create a new superuser and log in with it.

## Run

**HTTP + WebSocket (Daphne):**
```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

**HTTP only:**
```bash
python manage.py runserver
```

## API docs (Swagger)

- **Swagger UI:** http://localhost:8000/api/docs/
- **OpenAPI schema:** http://localhost:8000/api/schema/

## Auth & guest play

- **Register:** POST `username`, `email`, `password`, `password_confirm`.
- **Login:** POST `username` and `password` (not email). Returns `access` and `refresh` JWT.
- **Guest play:** No auth required. You can create a game (vs AI or local 2P), get game, make moves, get legal moves, and resign. Guest games are not tied to any account.
- **Account-only (require sign-in):** Game history (`GET /api/games/history/`), profile (`GET /api/users/profile/`), matchmaking (join/cancel). Ranked games and online matchmaking require an account.
- If you see "username already exists" but login fails, delete and re-register: `python manage.py delete_user <username>`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register/ | Register |
| POST | /api/auth/login/ | Login (JWT) |
| GET | /api/users/profile/ | Current user profile |
| POST | /api/matchmaking/join/ | Join queue (ranked/casual) |
| POST | /api/matchmaking/cancel/ | Leave queue |
| POST | /api/games/ | Create game (AI or wait) |
| GET | /api/games/{id}/ | Game state |
| POST | /api/games/{id}/move/ | Make move |
| GET | /api/games/{id}/legal-moves/?row=&col= | Legal moves for piece |
| POST | /api/games/{id}/resign/ | Resign |
| GET | /api/games/history/ | User game history |

## WebSocket

Connect: `ws://host:8000/ws/game/{game_id}/`

Events:
- `join_game` — request current game state
- `make_move` — `{from_row, from_col, to_row, to_col}`
- `resign` — resign game

Server sends:
- `game_state` — `{board, current_turn, status}`
- `move_update` — `{board, current_turn, winner, captured}`
- `game_over` — `{reason: "resign"}`

## Config

- `.env` — `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `REDIS_URL`, `USE_REDIS_CHANNELS`
- For PostgreSQL: `DATABASE_URL=postgres://user:pass@host:5432/dbname`
- For Redis channels: `USE_REDIS_CHANNELS=True` (default False uses InMemoryChannelLayer)
