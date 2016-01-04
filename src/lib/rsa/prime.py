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

'''Numerical functions related to primes.

Implementation based on the book Algorithm Design by Michael T. Goodrich and
Roberto Tamassia, 2002.
'''

__all__ = [ 'getprime', 'are_relatively_prime']

import rsa.randnum

def gcd(p, q):
    '''Returns the greatest common divisor of p and q

    >>> gcd(48, 180)
    12
    '''

    while q != 0:
        if p < q: (p,q) = (q,p)
        (p,q) = (q, p % q)
    return p
    

def jacobi(a, b):
    '''Calculates the value of the Jacobi symbol (a/b) where both a and b are
    positive integers, and b is odd

    :returns: -1, 0 or 1
    '''

    assert a > 0
    assert b > 0

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
    '''Returns False if n is an Euler pseudo-prime with base x, and
    True otherwise.
    '''

    j = jacobi(x, n) % n

    f = pow(x, n >> 1, n)

    if j == f: return False
    return True

def randomized_primality_testing(n, k):
    '''Calculates whether n is composite (which is always correct) or
    prime (which is incorrect with error probability 2**-k)

    Returns False if the number is composite, and True if it's
    probably prime.
    '''

    # 50% of Jacobi-witnesses can report compositness of non-prime numbers

    # The implemented algorithm using the Jacobi witness function has error
    # probability q <= 0.5, according to Goodrich et. al
    #
    # q = 0.5
    # t = int(math.ceil(k / log(1 / q, 2)))
    # So t = k / log(2, 2) = k / 1 = k
    # this means we can use range(k) rather than range(t)

    for _ in range(k):
        x = rsa.randnum.randint(n-1)
        if jacobi_witness(x, n): return False
    
    return True

def is_prime(number):
    '''Returns True if the number is prime, and False otherwise.

    >>> is_prime(42)
    False
    >>> is_prime(41)
    True
    '''

    return randomized_primality_testing(number, 6)

def getprime(nbits):
    '''Returns a prime number that can be stored in 'nbits' bits.

    >>> p = getprime(128)
    >>> is_prime(p-1)
    False
    >>> is_prime(p)
    True
    >>> is_prime(p+1)
    False
    
    >>> from rsa import common
    >>> common.bit_size(p) == 128
    True
    
    '''

    while True:
        integer = rsa.randnum.read_random_int(nbits)

        # Make sure it's odd
        integer |= 1

        # Test for primeness
        if is_prime(integer):
            return integer

        # Retry if not prime


def are_relatively_prime(a, b):
    '''Returns True if a and b are relatively prime, and False if they
    are not.

    >>> are_relatively_prime(2, 3)
    1
    >>> are_relatively_prime(2, 4)
    0
    '''

    d = gcd(a, b)
    return (d == 1)
    
if __name__ == '__main__':
    print('Running doctests 1000x or until failure')
    import doctest
    
    for count in range(1000):
        (failures, tests) = doctest.testmod()
        if failures:
            break
        
        if count and count % 100 == 0:
            print('%i times' % count)
    
    print('Doctests done')
