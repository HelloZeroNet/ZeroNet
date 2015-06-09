openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -nodes -config openssl.cnf
REM openssl ecparam -name secp521r1 -genkey -param_enc explicit -out key-ecc.pem -config openssl.cnf

openssl ecparam -name secp256r1 -genkey -out key-ecc.pem
openssl req -new -key key-ecc.pem -x509 -nodes -out cert-ecc.pem -config openssl.cnf

@echo off
REM openssl ecparam -genkey -name prime256v1 -out key.pem
REM openssl req -new -key key.pem -out csr.pem
REM openssl req -x509 -days 365 -key key.pem -in csr.pem -out certificate.pem