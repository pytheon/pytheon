from setuptools import setup, find_packages
import sys, os

version = '0.1'

install_requires=[
  'setuptools',
  'ConfigObject',
]

if 'WITH_KEYRING' in os.environ:
    install_requires.append('keyring')

if sys.version_info[:2] < (2, 6):
    install_requires.extend([
        'simplejson',
      ])

setup(name='pytheon',
      version=version,
      description="pytheon cli",
      long_description=open('README.txt').read(),
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='python hosting client',
      author='Pytheon Team',
      author_email='py@bearstech.com',
      url='http://docs.pytheon.net',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      namespace_packages=['pytheon'],
      include_package_data=True,
      zip_safe=True,
      install_requires=install_requires,
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      pytheon = pytheon.main:main
      """,
      )
