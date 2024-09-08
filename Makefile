dev:
	docker compose -f web-docker-compose.yaml up

test:
	docker-compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run pytest

shell:
	docker-compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run python manage.py shell

makemigrations:
	docker-compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run python manage.py makemigrations

migrate:
	docker-compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run python manage.py migrate

createsuperuser:
	docker compose -f web-docker-compose.yaml run --rm web python manage.py createsuperuser

format:
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run ruff format .
	docker compose -f test-services-docker-compose.yaml run --rm django-q2 poetry run ruff check . --fix
