dev:
	docker compose -f web-docker-compose.yaml up

build-test:
	docker compose -f test-services-docker-compose.yaml build --no-cache

lock:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv lock

test:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run pytest

shell:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run python manage.py shell

makemigrations:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run python manage.py makemigrations

migrate:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run python manage.py migrate

build-package:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run django-admin compilemessages
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv build

createsuperuser:
	docker compose -f web-docker-compose.yaml run --rm web python manage.py createsuperuser

format:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run ruff format .
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 uv run ruff check . --fix
