dev:
	docker compose -f web-docker-compose.yaml up

test:
	docker-compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run pytest

createsuperuser:
	docker compose -f web-docker-compose.yaml run --rm web python manage.py createsuperuser

format:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run ruff format .
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run ruff check . --fix
