FROM python:3.12

ENV PYTHONUNBUFFERED 1
RUN mkdir -p /app
WORKDIR /app
COPY . .
RUN pip install django blessed django-picklefield

