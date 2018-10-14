# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name="lyrebot",
    version="0.0.1",
    description="Lyrebird API bot",
    url="https://github.com/MartinHowarth/lyrebot",
    author="Martin Howarth",
    author_email="howarth.martin@gmail.com",
    license="MIT",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
    keywords="",
    packages=find_packages(exclude=["contrib", "docs", "tests*"]),
    install_requires=[
        'discord.py',
        'flask',
        'requests',
        'requests_oauthlib',
        'pyaudio',
        'pynacl',
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
)
