FROM python:3.11-alpine3.17

RUN pip install --no-cache-dir redis==4.5.3 flower==1.2.0

ENV PYTHONUNBUFFERED=1 PYTHONHASHSEED=random PYTHONDONTWRITEBYTECODE=1

EXPOSE 5555

WORKDIR /workdir

COPY flower.sh /workdir
CMD ["/workdir/flower.sh"]
