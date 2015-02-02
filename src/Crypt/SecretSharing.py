# -*- coding: utf-8 -*-
"""
    Secret Sharing
    ~~~~~

    :copyright: (c) 2014 by Halfmoon Labs
    :license: MIT, see LICENSE for more details.
"""

import os
from math import ceil
import string

def dev_random_entropy(numbytes):
    return open("/dev/random", "rb").read(numbytes)

def dev_urandom_entropy(numbytes):
    return open("/dev/urandom", "rb").read(numbytes)

def get_entropy(numbytes):
    if os.name == 'nt':
        return os.urandom(numbytes)
    else:
        return dev_random_entropy(numbytes)

def randint(min_value, max_value):
    """ Chooses a random integer between min_value and max_value, inclusive.
        Range of values: [min_value, max_value]
    """
    if not (isinstance(min_value, int) and isinstance(min_value, int)):
        raise ValueError('min and max must be integers')
    # Bounds are inclusive, so add 1 to the spread between the min and max
    value_range = (max_value - min_value) + 1
    # The bytes of entropy required depends on the bit length of the value range
    numbytes_of_entropy = int(ceil(value_range.bit_length()/8.0)) + 1
    # The entropy value range is the # of possible values of the entropy sample
    entropy_value_range = 2**(numbytes_of_entropy*8)
    # Any number greater than a multiple of the value range will be rejected
    acceptable_sample_range = entropy_value_range - (entropy_value_range % value_range)
    # Rejection sampling: Keep picking random #s until one falls in the range
    while True:
        byte_from_entropy = get_entropy(numbytes_of_entropy)
        int_from_entropy = int(byte_from_entropy.encode('hex'), 16)
        if int_from_entropy <= acceptable_sample_range:
            break
    # Take the sampled int and extract an int that's within the provided bounds
    rand_int = min_value + (int_from_entropy % value_range)
    return rand_int

def egcd(a, b):
    if a == 0:
        return (b, 0, 1)
    else:
        g, y, x = egcd(b % a, a)
        return (g, x - (b // a) * y, y)

def mod_inverse(k, prime):
    k = k % prime
    if k < 0:
        r = egcd(prime, -k)[2]
    else:
        r = egcd(prime, k)[2]
    return (prime + r) % prime

def random_polynomial(degree, intercept, upper_bound):
    """ Generates a random polynomial with positive coefficients.
    """
    if degree < 0:
        raise ValueError('Degree must be a non-negative number.')
    coefficients = [intercept]
    for i in range(degree):
        random_coeff = randint(0, upper_bound-1)
        coefficients.append(random_coeff)
    return coefficients

def get_polynomial_points(coefficients, num_points, prime):
    """ Calculates the first n polynomial points.
        [ (1, f(1)), (2, f(2)), ... (n, f(n)) ]
    """
    points = []
    for x in range(1, num_points+1):
        # start with x=1 and calculate the value of y
        y = coefficients[0]
        # calculate each term and add it to y, using modular math
        for i in range(1, len(coefficients)):
            exponentiation = (long(x)**i) % prime
            term = (coefficients[i] * exponentiation) % prime
            y = (y + term) % prime
        # add the point to the list of points
        points.append((x, y))
    return points

def modular_lagrange_interpolation(x, points, prime):
    # break the points up into lists of x and y values
    x_values, y_values = zip(*points)
    # initialize f(x) and begin the calculation: f(x) = SUM( y_i * l_i(x) )
    f_x = long(0)
    for i in range(len(points)):
        # evaluate the lagrange basis polynomial l_i(x)
        numerator, denominator = 1, 1
        for j in range(len(points)):
            # don't compute a polynomial fraction if i equals j
            if i == j: continue
            # compute a fraction and update the existing numerator + denominator
            numerator = (numerator * (x - x_values[j])) % prime
            denominator = (denominator * (x_values[i] - x_values[j])) % prime
        # get the polynomial from the numerator + mod inverse of the denominator
        lagrange_polynomial = numerator * mod_inverse(denominator, prime)
        # multiply the current y and the evaluated polynomial and add it to f(x)
        f_x = (prime + f_x + (y_values[i] * lagrange_polynomial)) % prime
    return f_x


def calculate_mersenne_primes():
    """ Returns all the mersenne primes with less than 500 digits.
        All primes:
        3, 7, 31, 127, 8191, 131071, 524287, 2147483647L, 2305843009213693951L,
        618970019642690137449562111L, 162259276829213363391578010288127L,
        170141183460469231731687303715884105727L,
        68647976601306097149...12574028291115057151L, (157 digits)
        53113799281676709868...70835393219031728127L, (183 digits)
        10407932194664399081...20710555703168729087L, (386 digits)
    """
    mersenne_prime_exponents = [
        2, 3, 5, 7, 13, 17, 19, 31, 61, 89, 107, 127, 521, 607, 1279
    ]
    primes = []
    for exp in mersenne_prime_exponents:
        prime = long(1)
        for i in range(exp):
            prime *= 2
        prime -= 1
        primes.append(prime)
    return primes

SMALLEST_257BIT_PRIME = (2**256 + 297)
SMALLEST_321BIT_PRIME = (2**320 + 27)
SMALLEST_385BIT_PRIME = (2**384 + 231)
STANDARD_PRIMES = calculate_mersenne_primes() + [
    SMALLEST_257BIT_PRIME, SMALLEST_321BIT_PRIME, SMALLEST_385BIT_PRIME
]
STANDARD_PRIMES.sort()

def get_large_enough_prime(batch):
    """ Returns a prime number that is greater all the numbers in the batch.
    """
    # build a list of primes
    primes = STANDARD_PRIMES
    # find a prime that is greater than all the numbers in the batch
    for prime in primes:
        numbers_greater_than_prime = [i for i in batch if i > prime]
        if len(numbers_greater_than_prime) == 0:
            return prime
    return None


def int_to_charset(x, charset):
    """ Turn a non-negative integer into a string.
    """
    if not (isinstance(x, (int, long)) and x >= 0):
        raise ValueError("x must be a non-negative integer.")
    if x == 0:
        return charset[0]
    output = ""
    while x > 0:
        x, digit = divmod(x, len(charset))
        output += charset[digit]
    # reverse the characters in the output and return
    return output[::-1]

def charset_to_int(s, charset):
    """ Turn a string into a non-negative integer.
    """
    if not isinstance(s, (str)):
        raise ValueError("s must be a string.")
    if (set(s) - set(charset)):
        raise ValueError("s has chars that aren't in the charset.")
    output = 0
    for char in s:
        output = output * len(charset) + charset.index(char)
    return output

def change_charset(s, original_charset, target_charset):
    """ Convert a string from one charset to another.
    """
    intermediate_integer = charset_to_int(s, original_charset)
    output_string = int_to_charset(intermediate_integer, target_charset)
    return output_string

""" Base16 includes numeric digits and the letters a through f. Here,
    we use the lowecase letters.
"""
base16_chars = string.hexdigits[0:16]

""" The Base58 character set allows for strings that avoid visual ambiguity
    when typed. It consists of all the alphanumeric characters except for
    "0", "O", "I", and "l", which look similar in some fonts.

    https://en.bitcoin.it/wiki/Base58Check_encoding
"""
base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

""" The Base32 character set allows for accurate transcribing by hand.
    It consists of uppercase letters + numerals, excluding "0", "1", + "8",
    which could look similar to "O", "I", and "B" and so are omitted.

    http://en.wikipedia.org/wiki/Base32
"""
base32_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

""" The z-base-32 character set is similar to the standard Base32 character
    set, except it uses lowercase letters + numerals and chooses to exclude
    "0", "l", "v", + "2". The set is also permuted so that easier chars
    occur more frequently.

    http://philzimmermann.com/docs/human-oriented-base-32-encoding.txt
"""
zbase32_chars = "ybndrfg8ejkmcpqxot1uwisza345h769"

""" The Base64 character set is a popular encoding for transmitting data
    over media that are designed for textual data. It includes all alphanumeric
    characters plus two bonus characters, usually "+" and "/".

    http://en.wikipedia.org/wiki/Base64
"""
base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def secret_int_to_points(secret_int, point_threshold, num_points):
    """ Split a secret (integer) into shares (pair of integers / x,y coords).

        Sample the points of a random polynomial with the y intercept equal to
        the secret int.
    """
    if point_threshold < 2:
        raise ValueError("Threshold must be >= 2.")
    if point_threshold > num_points:
        raise ValueError("Threshold must be < the total number of points.")
    prime = get_large_enough_prime([secret_int, num_points])
    if not prime:
        raise ValueError("Error! Secret is too long for share calculation!")
    coefficients = random_polynomial(point_threshold-1, secret_int, prime)
    points = get_polynomial_points(coefficients, num_points, prime)
    return points

def points_to_secret_int(points):
    """ Join int points into a secret int.

        Get the intercept of a random polynomial defined by the given points.
    """
    if not isinstance(points, list):
        raise ValueError("Points must be in list form.")
    for point in points:
        if not isinstance(point, tuple) and len(point) == 2:
            raise ValueError("Each point must be a tuple of two values.")
        if not isinstance(point[0], (int, long)) and \
            isinstance(point[1], (int, long)):
            raise ValueError("Each value in the point must be an int.")
    x_values, y_values = zip(*points)
    prime = get_large_enough_prime(y_values)
    free_coefficient = modular_lagrange_interpolation(0, points, prime)
    secret_int = free_coefficient # the secret int is the free coefficient
    return secret_int

def point_to_share_string(point, charset):
    """ Convert a point (a tuple of two integers) into a share string - that is,
        a representation of the point that uses the charset provided.
    """
    # point should be in the format (1, 4938573982723...)
    if '-' in charset:
        raise ValueError('The character "-" cannot be in the supplied charset.')
    if not isinstance(point, tuple) and len(point) == 2 and \
        isinstance(point[0], (int, long)) and isinstance(point[1], (int, long)):
        raise ValueError('Point format is invalid. Must be a pair of integers.')
    x,y = point
    x_string = int_to_charset(x, charset)
    y_string = int_to_charset(y, charset)
    share_string = x_string + '-' + y_string
    return share_string

def share_string_to_point(share_string, charset):
    """ Convert a share string to a point (a tuple of integers).
    """
    # share should be in the format "01-d051080de7..."
    if '-' in charset:
        raise ValueError('The character "-" cannot be in the supplied charset.')
    if not isinstance(share_string, str) and share_string.count('-') == 1:
        raise ValueError('Share format is invalid.')    
    x_string, y_string = share_string.split('-')
    if (set(x_string) - set(charset)) or (set(y_string) - set(charset)):
        raise ValueError("Share has characters that aren't in the charset.")
    x = charset_to_int(x_string, charset)
    y = charset_to_int(y_string, charset)
    return (x, y)

class SecretSharer():
    """ Creates a secret sharer, which can convert from a secret string to a
        list of shares and vice versa. The splitter is initialized with the
        character set of the secrets and the character set of the shares that it
        expects to be dealing with.
    """
    secret_charset = string.hexdigits[0:16]
    share_charset = string.hexdigits[0:16]

    def __init__(self):
        pass

    @classmethod
    def split_secret(cls, secret_string, share_threshold, num_shares):
        secret_int = charset_to_int(secret_string, cls.secret_charset)
        points = secret_int_to_points(secret_int, share_threshold, num_shares)
        shares = []
        for point in points:
            shares.append(point_to_share_string(point, cls.share_charset))
        return shares

    @classmethod
    def recover_secret(cls, shares):
        points = []
        for share in shares:
            points.append(share_string_to_point(share, cls.share_charset))
        secret_int = points_to_secret_int(points)
        secret_string = int_to_charset(secret_int, cls.secret_charset)
        return secret_string

class HexToHexSecretSharer(SecretSharer):
    """ Standard sharer for converting hex secrets to hex shares.
    """
    secret_charset = string.hexdigits[0:16]
    share_charset = string.hexdigits[0:16]

class PlaintextToHexSecretSharer(SecretSharer):
    """ Good for converting secret messages into standard hex shares.
    """
    secret_charset = string.printable
    share_charset = string.hexdigits[0:16]

class BitcoinToB58SecretSharer(SecretSharer):
    """ Good for converting Bitcoin secret keys into shares that can be
        reliably printed out in any font.
    """
    secret_charset = base58_chars
    share_charset = base58_chars

class BitcoinToB32SecretSharer(SecretSharer):
    """ Good for converting Bitcoin secret keys into shares that can be
        reliably and conveniently transcribed.
    """
    secret_charset = base58_chars
    share_charset = base32_chars

class BitcoinToZB32SecretSharer(SecretSharer):
    """ Good for converting Bitcoin secret keys into shares that can be
        reliably and conveniently transcribed.
    """
    secret_charset = base58_chars
    share_charset = zbase32_chars




