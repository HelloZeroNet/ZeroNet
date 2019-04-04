FROM alpine:3.8

#Base settings
ENV HOME /root

#Install ZeroNet
RUN apk --no-cache --no-progress add musl-dev gcc python python-dev py2-pip tor openssl \
 && pip install --no-cache-dir gevent msgpack \
 && apk del musl-dev gcc python-dev py2-pip \
 && echo "ControlPort 9051" >> /etc/tor/torrc \
 && echo "CookieAuthentication 1" >> /etc/tor/torrc

#Add Zeronet source
COPY . /root
VOLUME /root/data

#Control if Tor proxy is started
ENV ENABLE_TOR false

WORKDIR /root

#Set upstart command
CMD (! ${ENABLE_TOR} || tor&) && python zeronet.py --ui_ip 0.0.0.0 --fileserver_port 26552

#Expose ports
EXPOSE 43110 26552
