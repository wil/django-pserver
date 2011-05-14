from setuptools import setup, find_packages

from pserver import __version__


setup(
    name = "django-pserver",
    version = __version__,
    author = "Wil Tan",
    author_email = "wil@dready.org",
    description = "Django runserver replacement that reuses its listening socket on reload",
    license = "MIT/X",
    install_requires = [],
    packages = find_packages(),
)
