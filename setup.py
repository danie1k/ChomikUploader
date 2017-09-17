import sys
from distutils.core import setup

if sys.platform.startswith('win'):
    import py2exe

AUTHOR = __import__('src').__author__
LICENSE = __import__('src').__license__
VERSION = __import__('src').__version__

setup(
    name='ChomikUploader',
    version=VERSION,
    author=AUTHOR,
    license=LICENSE,
    description='Uploading files on Chomikuj.pl',
    package_dir={'chomikuploader': 'src'},
    packages=['chomikuploader'],
    options={
        'py2exe': {
            'compressed': True,
            'ignores': ['email.Iterators', 'email.Generator'],
            'bundle_files': 1
        },
        'sdist': {
            'formats': 'zip'
        }
    },
    scripts=['chomik'],
    console=['chomik'],
    zipfile=None,
    install_requires=[
        'dicttoxml>=1.7.4',
        'lxml>=3.8.0',
        'progressbar2>=3.34.2',
        'requests>=2.18.4',
        'traitlets>=4.3.2',
        'xmltodict>=0.11.0',
    ]
)
