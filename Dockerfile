FROM python:3.10.4-alpine

RUN apk --update --no-cache --no-progress add gcc libffi-dev musl-dev make tor openssl g++ \
 && echo "ControlPort 9051" >> /etc/tor/torrc \
 && echo "CookieAuthentication 1" >> /etc/tor/torrc

WORKDIR /app
VOLUME /app/data
COPY . .

RUN python3 -m venv venv \
 && source venv/bin/activate \
 && python3 -m pip install -r requirements.txt

ENV ENABLE_TOR false

CMD (! ${ENABLE_TOR} || tor&) \
 && source venv/bin/activate \
 && python3 zeronet.py --ui_ip "*" --fileserver_port 26552

EXPOSE 43110 26552
