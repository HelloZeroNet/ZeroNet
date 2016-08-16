FROM ubuntu:14.04

MAINTAINER Felix Imobersteg <felix@whatwedo.ch>

#Base settings
ENV DEBIAN_FRONTEND noninteractive
ENV HOME /root

#Install ZeroNet
RUN \
    apt-get update -y; \
    apt-get -y install msgpack-python python-gevent python-pip python-dev \
        wget libssl-dev libevent1-dev; \
    pip install msgpack-python --upgrade; \
    apt-get clean -y; \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#Install Tor
RUN wget https://www.torproject.org/dist/tor-0.2.7.6.tar.gz; \
    gzip -cd tor-0.2.7.6.tar.gz  | tar xfv -; \
    cd tor-0.2.7.6; \
    ./configure --disable-systemd; \
    make; \
    make install

#Setup Tor
RUN cat /usr/local/etc/tor/torrc.sample | \
        sed 's/#ControlPort/ControlPort/g' | \
        sed 's/#CookieAuthentication/CookieAuthentication/g' \
        >/usr/local/etc/tor/torrc;\
    cd /root; \
    mkdir /var/run/tor

#Add Zeronet source
ADD . /root
VOLUME /root/data

#Set upstart command
COPY docker_files/init /init
CMD /init

#Expose ports
EXPOSE 43110
EXPOSE 15441

