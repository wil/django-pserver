from setuptools import setup, find_packages

from pserver import __version__


setup(
    name = "django-pserver",
    version = __version__,
    author = "Wil Tan",
    author_email = "wil@dready.org",
    description = "Django runserver replacement that reuses its listening socket on reload",
    license = "MIT/X",
    # install_requires = ['Django>=1.3'],
    packages = find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Internet',
        'Framework :: Django',
    ]
)
