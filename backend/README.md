# FALCON backend

FastAPI application. Reads its settings from the `.env` file in the repository root.

```sh
uv run uvicorn app.main:app --reload --port 8010   # start the API (http://127.0.0.1:8010/api/docs)
uv run pytest                                      # run tests (uses a separate falcon_test database)
uv run alembic upgrade head                        # apply database migrations
uv run alembic revision --autogenerate -m "..."    # create a migration after changing models
uv run python -m app.scripts.seed_demo_users       # create fictional demo users (development)
uv run ruff check . && uv run ruff format .        # lint + format
```
