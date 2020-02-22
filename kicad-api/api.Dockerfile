# pull official base image
FROM python:3.9.1-slim-buster

# set work directory
WORKDIR /usr/src

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
RUN pip install flask celery redis

#COPY ./requirements.txt .
#RUN pip install -r requirements.txt

# copy project
#COPY src .
