# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""RSA module

Module for calculating large primes, and RSA encryption, decryption,
signing and verification. Includes generating public and private keys.

WARNING: this implementation does not use random padding, compression of the
cleartext input to prevent repetitions, or other common security improvements.
Use with care.

"""

__author__ = "Sybren Stuvel, Marloes de Boer, Ivo Tamboer, and Barry Mead"
__date__ = "2010-02-08"
__version__ = '2.0'

import math
import os
import random
import sys
import types
from rsa._compat import byte

# Display a warning that this insecure version is imported.
import warnings
warnings.warn('Insecure version of the RSA module is imported as %s' % __name__)


def bit_size(number):
    """Returns the number of bits required to hold a specific long number"""

    return int(math.ceil(math.log(number,2)))

def gcd(p, q):
    """Returns the greatest common divisor of p and q
    >>> gcd(48, 180)
    12
    """
    # Iterateive Version is faster and uses much less stack space
    while q != 0:
        if p < q: (p,q) = (q,p)
        (p,q) = (q, p % q)
    return p
    

def bytes2int(bytes):
    """Converts a list of bytes or a string to an integer

    >>> (((128 * 256) + 64) * 256) + 15
    8405007
    >>> l = [128, 64, 15]
    >>> bytes2int(l)              #same as bytes2int('\x80@\x0f')
    8405007
    """

    if not (type(bytes) is types.ListType or type(bytes) is types.StringType):
        raise TypeError("You must pass a string or a list")

    # Convert byte stream to integer
    integer = 0
    for byte in bytes:
        integer *= 256
        if type(byte) is types.StringType: byte = ord(byte)
        integer += byte

    return integer

def int2bytes(number):
    """
    Converts a number to a string of bytes
    """

    if not (type(number) is types.LongType or type(number) is types.IntType):
        raise TypeError("You must pass a long or an int")

    string = ""

    while number > 0:
        string = "%s%s" % (byte(number & 0xFF), string)
        number /= 256
    
    return string

def to64(number):
    """Converts a number in the range of 0 to 63 into base 64 digit
    character in the range of '0'-'9', 'A'-'Z', 'a'-'z','-','_'.
    
    >>> to64(10)
    'A'
    """

    if not (type(number) is types.LongType or type(number) is types.IntType):
        raise TypeError("You must pass a long or an int")

    if 0 <= number <= 9:            #00-09 translates to '0' - '9'
        return byte(number + 48)

    if 10 <= number <= 35:
        return byte(number + 55)     #10-35 translates to 'A' - 'Z'

    if 36 <= number <= 61:
        return byte(number + 61)     #36-61 translates to 'a' - 'z'

    if number == 62:                # 62   translates to '-' (minus)
        return byte(45)

    if number == 63:                # 63   translates to '_' (underscore)
        return byte(95)

    raise ValueError('Invalid Base64 value: %i' % number)


def from64(number):
    """Converts an ordinal character value in the range of
    0-9,A-Z,a-z,-,_ to a number in the range of 0-63.
    
    >>> from64(49)
    1
    """

    if not (type(number) is types.LongType or type(number) is types.IntType):
        raise TypeError("You must pass a long or an int")

    if 48 <= number <= 57:         #ord('0') - ord('9') translates to 0-9
        return(number - 48)

    if 65 <= number <= 90:         #ord('A') - ord('Z') translates to 10-35
        return(number - 55)

    if 97 <= number <= 122:        #ord('a') - ord('z') translates to 36-61
        return(number - 61)

    if number == 45:               #ord('-') translates to 62
        return(62)

    if number == 95:               #ord('_') translates to 63
        return(63)

    raise ValueError('Invalid Base64 value: %i' % number)


def int2str64(number):
    """Converts a number to a string of base64 encoded characters in
    the range of '0'-'9','A'-'Z,'a'-'z','-','_'.
    
    >>> int2str64(123456789)
    '7MyqL'
    """

    if not (type(number) is types.LongType or type(number) is types.IntType):
        raise TypeError("You must pass a long or an int")

    string = ""

    while number > 0:
        string = "%s%s" % (to64(number & 0x3F), string)
        number /= 64

    return string


def str642int(string):
    """Converts a base64 encoded string into an integer.
    The chars of this string in in the range '0'-'9','A'-'Z','a'-'z','-','_'
    
    >>> str642int('7MyqL')
    123456789
    """

    if not (type(string) is types.ListType or type(string) is types.StringType):
        raise TypeError("You must pass a string or a list")

    integer = 0
    for byte in string:
        integer *= 64
        if type(byte) is types.StringType: byte = ord(byte)
        integer += from64(byte)

    return integer

def read_random_int(nbits):
    """Reads a random integer of approximately nbits bits rounded up
    to whole bytes"""

    nbytes = int(math.ceil(nbits/8.))
    randomdata = os.urandom(nbytes)
    return bytes2int(randomdata)

def randint(minvalue, maxvalue):
    """Returns a random integer x with minvalue <= x <= maxvalue"""

    # Safety - get a lot of random data even if the range is fairly
    # small
    min_nbits = 32

    # The range of the random numbers we need to generate
    range = (maxvalue - minvalue) + 1

    # Which is this number of bytes
    rangebytes = ((bit_size(range) + 7) / 8)

    # Convert to bits, but make sure it's always at least min_nbits*2
    rangebits = max(rangebytes * 8, min_nbits * 2)
    
    # Take a random number of bits between min_nbits and rangebits
    nbits = random.randint(min_nbits, rangebits)
    
    return (read_random_int(nbits) % range) + minvalue

def jacobi(a, b):
    """Calculates the value of the Jacobi symbol (a/b)
    where both a and b are positive integers, and b is odd
    """

    if a == 0: return 0
    result = 1
    while a > 1:
        if a & 1:
            if ((a-1)*(b-1) >> 2) & 1:
                result = -result
            a, b = b % a, a
        else:
            if (((b * b) - 1) >> 3) & 1:
                result = -result
            a >>= 1
    if a == 0: return 0
    return result

def jacobi_witness(x, n):
    """Returns False if n is an Euler pseudo-prime with base x, and
    True otherwise.
    """

    j = jacobi(x, n) % n
    f = pow(x, (n-1)/2, n)

    if j == f: return False
    return True

def randomized_primality_testing(n, k):
    """Calculates whether n is composite (which is always correct) or
    prime (which is incorrect with error probability 2**-k)

    Returns False if the number is composite, and True if it's
    probably prime.
    """

    # 50% of Jacobi-witnesses can report compositness of non-prime numbers

    for i in range(k):
        x = randint(1, n-1)
        if jacobi_witness(x, n): return False
    
    return True

def is_prime(number):
    """Returns True if the number is prime, and False otherwise.

    >>> is_prime(42)
    0
    >>> is_prime(41)
    1
    """

    if randomized_primality_testing(number, 6):
        # Prime, according to Jacobi
        return True
    
    # Not prime
    return False

    
def getprime(nbits):
    """Returns a prime number of max. 'math.ceil(nbits/8)*8' bits. In
    other words: nbits is rounded up to whole bytes.

    >>> p = getprime(8)
    >>> is_prime(p-1)
    0
    >>> is_prime(p)
    1
    >>> is_prime(p+1)
    0
    """

    while True:
        integer = read_random_int(nbits)

        # Make sure it's odd
        integer |= 1

        # Test for primeness
        if is_prime(integer): break

        # Retry if not prime

    return integer

def are_relatively_prime(a, b):
    """Returns True if a and b are relatively prime, and False if they
    are not.

    >>> are_relatively_prime(2, 3)
    1
    >>> are_relatively_prime(2, 4)
    0
    """

    d = gcd(a, b)
    return (d == 1)

def find_p_q(nbits):
    """Returns a tuple of two different primes of nbits bits"""
    pbits = nbits + (nbits/16)  #Make sure that p and q aren't too close
    qbits = nbits - (nbits/16)  #or the factoring programs can factor n
    p = getprime(pbits)
    while True:
        q = getprime(qbits)
        #Make sure p and q are different.
        if not q == p: break
    return (p, q)

def extended_gcd(a, b):
    """Returns a tuple (r, i, j) such that r = gcd(a, b) = ia + jb
    """
    # r = gcd(a,b) i = multiplicitive inverse of a mod b
    #      or      j = multiplicitive inverse of b mod a
    # Neg return values for i or j are made positive mod b or a respectively
    # Iterateive Version is faster and uses much less stack space
    x = 0
    y = 1
    lx = 1
    ly = 0
    oa = a                             #Remember original a/b to remove 
    ob = b                             #negative values from return results
    while b != 0:
        q = long(a/b)
        (a, b)  = (b, a % b)
        (x, lx) = ((lx - (q * x)),x)
        (y, ly) = ((ly - (q * y)),y)
    if (lx < 0): lx += ob              #If neg wrap modulo orignal b
    if (ly < 0): ly += oa              #If neg wrap modulo orignal a
    return (a, lx, ly)                 #Return only positive values

# Main function: calculate encryption and decryption keys
def calculate_keys(p, q, nbits):
    """Calculates an encryption and a decryption key for p and q, and
    returns them as a tuple (e, d)"""

    n = p * q
    phi_n = (p-1) * (q-1)

    while True:
        # Make sure e has enough bits so we ensure "wrapping" through
        # modulo n
        e = max(65537,getprime(nbits/4))
        if are_relatively_prime(e, n) and are_relatively_prime(e, phi_n): break

    (d, i, j) = extended_gcd(e, phi_n)

    if not d == 1:
        raise Exception("e (%d) and phi_n (%d) are not relatively prime" % (e, phi_n))
    if (i < 0):
        raise Exception("New extended_gcd shouldn't return negative values")
    if not (e * i) % phi_n == 1:
        raise Exception("e (%d) and i (%d) are not mult. inv. modulo phi_n (%d)" % (e, i, phi_n))

    return (e, i)


def gen_keys(nbits):
    """Generate RSA keys of nbits bits. Returns (p, q, e, d).

    Note: this can take a long time, depending on the key size.
    """

    (p, q) = find_p_q(nbits)
    (e, d) = calculate_keys(p, q, nbits)

    return (p, q, e, d)

def newkeys(nbits):
    """Generates public and private keys, and returns them as (pub,
    priv).

    The public key consists of a dict {e: ..., , n: ....). The private
    key consists of a dict {d: ...., p: ...., q: ....).
    """
    nbits = max(9,nbits)           # Don't let nbits go below 9 bits
    (p, q, e, d) = gen_keys(nbits)

    return ( {'e': e, 'n': p*q}, {'d': d, 'p': p, 'q': q} )

def encrypt_int(message, ekey, n):
    """Encrypts a message using encryption key 'ekey', working modulo n"""

    if type(message) is types.IntType:
        message = long(message)

    if not type(message) is types.LongType:
        raise TypeError("You must pass a long or int")

    if message < 0 or message > n:
        raise OverflowError("The message is too long")

    #Note: Bit exponents start at zero (bit counts start at 1) this is correct
    safebit = bit_size(n) - 2                   #compute safe bit (MSB - 1)
    message += (1 << safebit)                   #add safebit to ensure folding

    return pow(message, ekey, n)

def decrypt_int(cyphertext, dkey, n):
    """Decrypts a cypher text using the decryption key 'dkey', working
    modulo n"""

    message = pow(cyphertext, dkey, n)

    safebit = bit_size(n) - 2                   #compute safe bit (MSB - 1)
    message -= (1 << safebit)                   #remove safebit before decode

    return message

def encode64chops(chops):
    """base64encodes chops and combines them into a ',' delimited string"""

    chips = []                              #chips are character chops

    for value in chops:
        chips.append(int2str64(value))

    #delimit chops with comma
    encoded = ','.join(chips)

    return encoded

def decode64chops(string):
    """base64decodes and makes a ',' delimited string into chops"""

    chips = string.split(',')               #split chops at commas

    chops = []

    for string in chips:                    #make char chops (chips) into chops
        chops.append(str642int(string))

    return chops

def chopstring(message, key, n, funcref):
    """Chops the 'message' into integers that fit into n,
    leaving room for a safebit to be added to ensure that all
    messages fold during exponentiation.  The MSB of the number n
    is not independant modulo n (setting it could cause overflow), so
    use the next lower bit for the safebit.  Therefore reserve 2-bits
    in the number n for non-data bits.  Calls specified encryption
    function for each chop.

    Used by 'encrypt' and 'sign'.
    """

    msglen = len(message)
    mbits = msglen * 8
    #Set aside 2-bits so setting of safebit won't overflow modulo n.
    nbits = bit_size(n) - 2             # leave room for safebit
    nbytes = nbits / 8
    blocks = msglen / nbytes

    if msglen % nbytes > 0:
        blocks += 1

    cypher = []
    
    for bindex in range(blocks):
        offset = bindex * nbytes
        block = message[offset:offset+nbytes]
        value = bytes2int(block)
        cypher.append(funcref(value, key, n))

    return encode64chops(cypher)   #Encode encrypted ints to base64 strings

def gluechops(string, key, n, funcref):
    """Glues chops back together into a string.  calls
    funcref(integer, key, n) for each chop.

    Used by 'decrypt' and 'verify'.
    """
    message = ""

    chops = decode64chops(string)  #Decode base64 strings into integer chops
    
    for cpart in chops:
        mpart = funcref(cpart, key, n) #Decrypt each chop
        message += int2bytes(mpart)    #Combine decrypted strings into a msg
    
    return message

def encrypt(message, key):
    """Encrypts a string 'message' with the public key 'key'"""
    if 'n' not in key:
        raise Exception("You must use the public key with encrypt")

    return chopstring(message, key['e'], key['n'], encrypt_int)

def sign(message, key):
    """Signs a string 'message' with the private key 'key'"""
    if 'p' not in key:
        raise Exception("You must use the private key with sign")

    return chopstring(message, key['d'], key['p']*key['q'], encrypt_int)

def decrypt(cypher, key):
    """Decrypts a string 'cypher' with the private key 'key'"""
    if 'p' not in key:
        raise Exception("You must use the private key with decrypt")

    return gluechops(cypher, key['d'], key['p']*key['q'], decrypt_int)

def verify(cypher, key):
    """Verifies a string 'cypher' with the public key 'key'"""
    if 'n' not in key:
        raise Exception("You must use the public key with verify")

    return gluechops(cypher, key['e'], key['n'], decrypt_int)

# Do doctest if we're not imported
if __name__ == "__main__":
    import doctest
    doctest.testmod()

__all__ = ["newkeys", "encrypt", "decrypt", "sign", "verify"]

