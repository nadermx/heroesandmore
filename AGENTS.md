# Repository Guidelines

## Project Structure & Module Organization
- `app/` holds Django settings and project configuration.
- Feature apps live at the repo root: `accounts/`, `items/`, `marketplace/`, `pricing/`, `alerts/`, `scanner/`, `seller_tools/`, `social/`, `user_collections/`, plus the shared `api/` app.
- Templates and static assets live in `templates/` and `static/`; user-uploaded media goes to `media/`.
- Deployment automation is in `ansible/`. Local overrides belong in `config.py` (created from `config.py.example`).
- Tests live in `{app}/tests/` and `api/tests/` (e.g., `marketplace/tests/test_listings.py`).

## Build, Test, and Development Commands
- `source venv/bin/activate` to enter the virtualenv.
- `cp config.py.example config.py` then update secrets for local settings.
- `python manage.py migrate` to apply database migrations (SQLite by default for local dev).
- `python manage.py runserver` to start the web app at `http://localhost:8000`.
- `celery -A app worker -l info` and `celery -A app beat -l info` to run background tasks.

## Coding Style & Naming Conventions
- Python code follows standard Django/PEP 8 conventions with 4‑space indentation.
- Keep app-specific code within its app directory; shared API code belongs in `api/` or `{app}/api/`.
- Tests use `test_*.py` filenames and `Test*`/`test_*` naming for classes and methods.

## Testing Guidelines
- Use Django’s test runner: `python manage.py test`.
- Run a single app: `python manage.py test marketplace`.
- Run a module/class/test: `python manage.py test marketplace.tests.test_listings.BiddingTests.test_bid_on_auction`.
- Tests use SQLite in-memory and mock external services (e.g., Stripe) as shown in existing tests.

## Commit & Pull Request Guidelines
- Commit messages in history are short, imperative summaries (e.g., “Add comprehensive test suite…”). Keep that style.
- No formal PR template is enforced; include a clear description, list of tests run, and screenshots for UI changes.

## Security & Configuration Tips
- Do not commit secrets. Use `config.py` for local keys and `ansible/group_vars/vault.yml` for deployments.
- Stripe and external service calls should be mocked in tests.
