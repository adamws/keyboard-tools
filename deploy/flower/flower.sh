#!/bin/sh

until timeout 5s celery inspect ping; do
    >&2 echo "Celery workers not available"
done

echo "Starting flower"
celery --broker=${CELERY_BROKER_URL} flower
