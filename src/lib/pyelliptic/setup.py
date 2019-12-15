from setuptools import setup, find_packages

setup(
    name="pyelliptic",
    version='2.0.1',
    url='https://github.com/radfish/pyelliptic',
    license='GPL',
    description="Python OpenSSL wrapper for ECC (ECDSA, ECIES), AES, HMAC, Blowfish, ...",
    author='Yann GUIBET',
    author_email='yannguibet@gmail.com',
    maintainer="redfish",
    maintainer_email='redfish@galactica.pw',
    packages=find_packages(),
    classifiers=[
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Environment :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.7',
        'Topic :: Security :: Cryptography',
    ],
)
