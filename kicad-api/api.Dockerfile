# pull official base image
FROM python:3.9.1-slim-buster

# set work directory
WORKDIR /usr/src

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip

COPY ./api-requirements.txt .
RUN pip install -r api-requirements.txt

# copy project
#COPY src .
