FROM alpine:3.8

#Base settings
ENV HOME /root

COPY requirements.txt /root/requirements.txt

#Install ZeroNet
RUN apk --no-cache --no-progress add python3 python3-dev gcc libffi-dev musl-dev make tor openssl \
 && pip3 install -r /root/requirements.txt \
 && apk del python3-dev gcc libffi-dev musl-dev make \
 && echo "ControlPort 9051" >> /etc/tor/torrc \
 && echo "CookieAuthentication 1" >> /etc/tor/torrc

#Add Zeronet source
COPY . /root
VOLUME /root/data

#Control if Tor proxy is started
ENV ENABLE_TOR false

WORKDIR /root

#Set upstart command
CMD (! ${ENABLE_TOR} || tor&) && python3 zeronet.py --ui_ip 0.0.0.0 --fileserver_port 26552

#Expose ports
EXPOSE 43110 26552
