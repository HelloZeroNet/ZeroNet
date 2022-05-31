FROM python:3.10.4-alpine

RUN apk --update --no-cache --no-progress add gcc libffi-dev musl-dev make openssl g++

WORKDIR /app
COPY . .

RUN python3 -m venv venv \
 && source venv/bin/activate \
 && python3 -m pip install -r requirements.txt

CMD source venv/bin/activate \
 && python3 zeronet.py --ui_ip "*" --fileserver_port 26552 \
    --tor $TOR_ENABLED --tor_controller tor:$TOR_CONTROL_PORT \
    --tor_proxy tor:$TOR_SOCKS_PORT --tor_password $TOR_CONTROL_PASSWD main

EXPOSE 43110 26552
