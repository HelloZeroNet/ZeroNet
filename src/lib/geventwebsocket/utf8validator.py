###############################################################################
##
##  Copyright 2011-2013 Tavendo GmbH
##
##  Note:
##
##  This code is a Python implementation of the algorithm
##
##            "Flexible and Economical UTF-8 Decoder"
##
##  by Bjoern Hoehrmann
##
##       bjoern@hoehrmann.de
##       http://bjoern.hoehrmann.de/utf-8/decoder/dfa/
##
##  Licensed under the Apache License, Version 2.0 (the "License");
##  you may not use this file except in compliance with the License.
##  You may obtain a copy of the License at
##
##      http://www.apache.org/licenses/LICENSE-2.0
##
##  Unless required by applicable law or agreed to in writing, software
##  distributed under the License is distributed on an "AS IS" BASIS,
##  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##  See the License for the specific language governing permissions and
##  limitations under the License.
##
###############################################################################


## use Cython implementation of UTF8 validator if available
##
try:
    from wsaccel.utf8validator import Utf8Validator
except:
    ## fallback to pure Python implementation

    class Utf8Validator:
        """
        Incremental UTF-8 validator with constant memory consumption (minimal
        state).

        Implements the algorithm "Flexible and Economical UTF-8 Decoder" by
        Bjoern Hoehrmann (http://bjoern.hoehrmann.de/utf-8/decoder/dfa/).
        """

        ## DFA transitions
        UTF8VALIDATOR_DFA = [
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  # 00..1f
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  # 20..3f
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  # 40..5f
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  # 60..7f
            1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,  # 80..9f
            7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,  # a0..bf
            8,8,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,  # c0..df
            0xa,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x4,0x3,0x3,  # e0..ef
            0xb,0x6,0x6,0x6,0x5,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,  # f0..ff
            0x0,0x1,0x2,0x3,0x5,0x8,0x7,0x1,0x1,0x1,0x4,0x6,0x1,0x1,0x1,0x1,  # s0..s0
            1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,0,1,0,1,1,1,1,1,1,  # s1..s2
            1,2,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,  # s3..s4
            1,2,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,3,1,1,1,1,1,1,  # s5..s6
            1,3,1,1,1,1,1,3,1,3,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,  # s7..s8
        ]

        UTF8_ACCEPT = 0
        UTF8_REJECT = 1

        def __init__(self):
            self.reset()

        def decode(self, b):
            """
            Eat one UTF-8 octet, and validate on the fly.

            Returns UTF8_ACCEPT when enough octets have been consumed, in which case
            self.codepoint contains the decoded Unicode code point.

            Returns UTF8_REJECT when invalid UTF-8 was encountered.

            Returns some other positive integer when more octets need to be eaten.
            """
            type = Utf8Validator.UTF8VALIDATOR_DFA[b]

            if self.state != Utf8Validator.UTF8_ACCEPT:
                self.codepoint = (b & 0x3f) | (self.codepoint << 6)
            else:
                self.codepoint = (0xff >> type) & b

            self.state = Utf8Validator.UTF8VALIDATOR_DFA[256 + self.state * 16 + type]

            return self.state

        def reset(self):
            """
            Reset validator to start new incremental UTF-8 decode/validation.
            """
            self.state = Utf8Validator.UTF8_ACCEPT
            self.codepoint = 0
            self.i = 0

        def validate(self, ba):
            """
            Incrementally validate a chunk of bytes provided as string.

            Will return a quad (valid?, endsOnCodePoint?, currentIndex, totalIndex).

            As soon as an octet is encountered which renders the octet sequence
            invalid, a quad with valid? == False is returned. currentIndex returns
            the index within the currently consumed chunk, and totalIndex the
            index within the total consumed sequence that was the point of bail out.
            When valid? == True, currentIndex will be len(ba) and totalIndex the
            total amount of consumed bytes.
            """

            l = len(ba)

            for i in xrange(l):
                ## optimized version of decode(), since we are not interested in actual code points

                self.state = Utf8Validator.UTF8VALIDATOR_DFA[256 + (self.state << 4) + Utf8Validator.UTF8VALIDATOR_DFA[ord(ba[i])]]

                if self.state == Utf8Validator.UTF8_REJECT:
                    self.i += i
                    return False, False, i, self.i

            self.i += l

            return True, self.state == Utf8Validator.UTF8_ACCEPT, l, self.i
