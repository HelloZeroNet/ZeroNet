# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Numerical functions related to primes.

Implementation based on the book Algorithm Design by Michael T. Goodrich and
Roberto Tamassia, 2002.
"""

import rsa.randnum

__all__ = ['getprime', 'are_relatively_prime']


def gcd(p, q):
    """Returns the greatest common divisor of p and q

    >>> gcd(48, 180)
    12
    """

    while q != 0:
        (p, q) = (q, p % q)
    return p


def miller_rabin_primality_testing(n, k):
    """Calculates whether n is composite (which is always correct) or prime
    (which theoretically is incorrect with error probability 4**-k), by
    applying Miller-Rabin primality testing.

    For reference and implementation example, see:
    https://en.wikipedia.org/wiki/Miller%E2%80%93Rabin_primality_test

    :param n: Integer to be tested for primality.
    :type n: int
    :param k: Number of rounds (witnesses) of Miller-Rabin testing.
    :type k: int
    :return: False if the number is composite, True if it's probably prime.
    :rtype: bool
    """

    # prevent potential infinite loop when d = 0
    if n < 2:
        return False

    # Decompose (n - 1) to write it as (2 ** r) * d
    # While d is even, divide it by 2 and increase the exponent.
    d = n - 1
    r = 0

    while not (d & 1):
        r += 1
        d >>= 1

    # Test k witnesses.
    for _ in range(k):
        # Generate random integer a, where 2 <= a <= (n - 2)
        a = rsa.randnum.randint(n - 4) + 2

        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue

        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == 1:
                # n is composite.
                return False
            if x == n - 1:
                # Exit inner loop and continue with next witness.
                break
        else:
            # If loop doesn't break, n is composite.
            return False

    return True


def is_prime(number):
    """Returns True if the number is prime, and False otherwise.

    >>> is_prime(2)
    True
    >>> is_prime(42)
    False
    >>> is_prime(41)
    True
    >>> [x for x in range(901, 1000) if is_prime(x)]
    [907, 911, 919, 929, 937, 941, 947, 953, 967, 971, 977, 983, 991, 997]
    """

    # Check for small numbers.
    if number < 10:
        return number in [2, 3, 5, 7]

    # Check for even numbers.
    if not (number & 1):
        return False

    # According to NIST FIPS 186-4, Appendix C, Table C.3, minimum number of
    # rounds of M-R testing, using an error probability of 2 ** (-100), for
    # different p, q bitsizes are:
    #   * p, q bitsize: 512; rounds: 7
    #   * p, q bitsize: 1024; rounds: 4
    #   * p, q bitsize: 1536; rounds: 3
    # See: http://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf
    return miller_rabin_primality_testing(number, 7)


def getprime(nbits):
    """Returns a prime number that can be stored in 'nbits' bits.

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
    """

    assert nbits > 3  # the loop wil hang on too small numbers

    while True:
        integer = rsa.randnum.read_random_odd_int(nbits)

        # Test for primeness
        if is_prime(integer):
            return integer

            # Retry if not prime


def are_relatively_prime(a, b):
    """Returns True if a and b are relatively prime, and False if they
    are not.

    >>> are_relatively_prime(2, 3)
    True
    >>> are_relatively_prime(2, 4)
    False
    """

    d = gcd(a, b)
    return d == 1


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
