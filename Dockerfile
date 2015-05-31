FROM ubuntu:14.04

MAINTAINER Felix Imobersteg <felix@whatwedo.ch>

#Base settings
ENV DEBIAN_FRONTEND noninteractive
ENV HOME /root

#Update package lists
RUN apt-get update -y

#Install ZeroNet deps
RUN apt-get install msgpack-python python-gevent python-pip python-dev -y
RUN pip install msgpack-python --upgrade

#Add Zeronet source
ADD . /root

#Slimming down Docker containers
RUN apt-get clean -y
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#Set upstart command
CMD cd /root && python zeronet.py --ui_ip 0.0.0.0

#Expose ports
EXPOSE 43110
EXPOSE 15441