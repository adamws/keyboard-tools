FROM python:3.8.9-alpine3.12

RUN apk add --no-cache curl jq

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY e2e-tests pytest.ini wait-for-selenium.sh /tests/

WORKDIR /tests

CMD ["./wait-for-selenium.sh", "pytest", "-s"]
