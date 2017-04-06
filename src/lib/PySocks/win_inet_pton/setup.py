from distutils.core import setup

setup (
    name = 'win_inet_pton',
    version = '1.0.1',
    py_modules = ['win_inet_pton'],
    url = 'https://github.com/hickeroar/win_inet_pton',
    author = 'Ryan Vennell',
    author_email = 'ryan.vennell@gmail.com',
    description = 'Native inet_pton and inet_ntop implementation for Python on Windows (with ctypes).',
    license = open('LICENSE', 'r').read(),
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities'
    ]
)