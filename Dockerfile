FROM alpine:3.15 

#Base settings
ENV HOME /root

COPY requirements.txt /root/requirements.txt

#Install ZeroNet
RUN apk --update --no-cache --no-progress add python3 python3-dev py3-pip gcc g++ autoconf automake libtool libffi-dev musl-dev make tor openssl \
 && pip3 install -r /root/requirements.txt \
 && apk del python3-dev gcc g++ autoconf automake libtool libffi-dev musl-dev make \
 && echo "ControlPort 9051" >> /etc/tor/torrc \
 && echo "CookieAuthentication 1" >> /etc/tor/torrc
 
RUN python3 -V \
 && python3 -m pip list \
 && tor --version \
 && openssl version

#Add Zeronet source
COPY . /root
VOLUME /root/data

#Control if Tor proxy is started
ENV ENABLE_TOR true

WORKDIR /root

#Set upstart command
CMD (! ${ENABLE_TOR} || tor&) && python3 zeronet.py --ui_ip 0.0.0.0 --fileserver_port 26117

#Expose ports
EXPOSE 43110 26117
