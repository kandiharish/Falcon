# FALCON backend

FastAPI application. Reads its settings from the `.env` file in the repository root.

```sh
uv run uvicorn app.main:app --reload --port 8010   # start the API (http://127.0.0.1:8010/api/docs)
uv run pytest                                      # run tests (needs the database running)
uv run ruff check . && uv run ruff format .        # lint + format
```
