#################################################
#                                               #
# Sample configuration file for MOCKS 0.0.2     #
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~     #
#                                               #
# I recommend reading the examples in this file #
# and then extending it to suite your needs.    #
#                                               #
#################################################



#########################
#                       
# General daemon config 
# ~~~~~~~~~~~~~~~~~~~~~ 
#                       
#########################

PORT 			= 1081       # Port MOCKS is to listen to
MOCKS_ADDR              = 127.0.0.1     # IP adress MOCKS is to bind to
LOG_FILE 		= mocks.log   # MOCKS log file
PID_FILE 		= mocks.pid   # File holding MOCKS's process ID
BUFFER_SIZE 		= 65536       # Traffic buffer size in bytes
BACKLOG     		= 5           # Backlog for listen()
NEGOTIATION_TIMEOUT 	= 5           
CONNECTION_IDLE_TIMEOUT = 300
BIND_TIMEOUT		= 30
SHUTDOWN_TIMEOUT	= 3
MAX_CONNECTIONS	        = 50



##########################################################################
#
# Client filter config
# ~~~~~~~~~~~~~~~~~~~~
#
#     Client filtering means sorting out which clients are allowed
# connection and which are not. This is basically done like this:
# MOCKS has a default behaviour regarding filtering client
# connections. This behaviour is called the 'policy' and can either
# be to ALLOW or to DENY the connection. After setting the policy
# you can specify a list of exceptions. The action MOCKS takes
# for a client matching any of these exceptions is the opposite
# of the policy (that is, if the policy is set to ALLOW the exceptions
# are denied and if the policy is set to DENY the exceptions are allowed).
#     An exception is specified in the form ip_address/mask, where mask
# is optional and is an integer ranging from 0 to 32 identifying the
# number of common heading bits that ip_address and the client's IP
# address must have in order to yield a match. If mask is missing,
# 32 will be assumed. For instance, 192.168.1.0/24 will match any IP
# ranging from 192.168.1.1 to 192.168.1.255.
#
#     Let's take two examples, one for each type of policy. Let's say we
# only want to allow IPs 10.12.0.0 through 10.12.255.255, 172.23.2.5 and
# 192.168.52.26 to use MOCKS. What we have to to is this:
#
# FILTER_POLICY    = DENY
# FILTER_EXCEPTION = 10.12.0.0/16
# FILTER_EXCEPTION = 172.23.2.5     # implied /32
# FILTER_EXCEPTION = 192.168.52.26  # implied /32
#
#     Now, let's say this is a public proxy server, but for some reason
# you don't want to let any IP ranging from 192.168.1.1 to 192.168.1.255
# and neither 10.2.5.13 to connect to it:
#
# FILTER_POLICY    = ALLOW
# FILTER_EXCEPTION = 192.168.1.0/24
# FILTER_EXCEPTION = 10.2.5.13
#
###########################################################################

FILTER_POLICY    = ALLOW



#############################################################################
#
# Upstream proxy config
# ~~~~~~~~~~~~~~~~~~~~~
# 
#     You can choose to further relay traffic through another proxy server.
# MOCKS supports upstream HTTP CONNECT, SOCKS4 and SOCKS5 proxies. You
# must specify the proxy type (one of HTTPCONNECT, SOCKS4 or SOCKS5), the
# proxy address and the proxy port. Optionally you can specify an user
# name and a password used to authenicate to the upstream proxy. This is
# pretty straight forward, so let's just take an example. Let's say you
# want to use the HTTP CONNECT server at httpconnectproxy.com, on port 3128,
# using the username 'foo' and the password 'bar'. You do it like this:
#
# UP_PROXY_TYPE   = HTTPCONNECT
# UP_PROXY_ADDR   = httpconnectproxy.com
# UP_PROXY_PORT   = 3128
# UP_PROXY_USER   = foo                   # These two can be missing if you
# UP_PROXY_PASSWD = bar                   # are not required to authenticate
#
#############################################################################

# UP_PROXY_TYPE   = HTTPCONNECT
# UP_PROXY_ADDR   = 192.168.1.12
# UP_PROXY_PORT   = 3128


