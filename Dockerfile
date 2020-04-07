FROM alpine:3.11 

# Base settings
ENV HOME /root
WORKDIR /root

# Install and configure dependencies
COPY requirements.txt /root/requirements.txt
RUN apk --update --no-cache --no-progress add python3 python3-dev gcc libffi-dev musl-dev make tor openssl \
 && pip3 install -r requirements.txt \
 && for PLUGIN in $(ls plugins/[^disabled-]*/requirements.txt); do pip3 install -r ${PLUGIN}; done \
 && apk del python3-dev gcc libffi-dev musl-dev make \
 && echo "ControlPort 9051" >> /etc/tor/torrc \
 && echo "CookieAuthentication 1" >> /etc/tor/torrc

# Add ZeroNet source
COPY . /root
VOLUME /root/data

# Control if Tor proxy is started
ENV ENABLE_TOR false

# Set upstart command
CMD (! ${ENABLE_TOR} || tor&) && python3 zeronet.py --ui_ip 0.0.0.0 --fileserver_port 26552

# Expose ports
EXPOSE 43110 26552
