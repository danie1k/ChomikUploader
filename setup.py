import sys
from distutils.core import setup

if sys.platform.startswith('win'):
    import py2exe

AUTHOR = __import__('src').__author__
EMAIL = __import__('src').__email__
LICENSE = __import__('src').__license__
VERSION = __import__('src').__version__

setup(
    name='ChomikUploader',
    version=VERSION,
    author=AUTHOR,
    author_email='dnk@dnk.net.pl',
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
        'xmltodict>=0.11.0'
    ]
)
