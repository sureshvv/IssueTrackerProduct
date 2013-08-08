import os.path
from setuptools import setup, find_packages

name = 'IssueTrackerProduct'
version = '0.14.3.dev0'

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

setup(name='IssueTrackerProduct',
      version=version,
      description="Bug/issue tracker for Zope2.",
      long_description=read("README.txt") + \
                       read("docs", "CHANGES.txt"),
      classifiers=[
        "Framework :: Zope2",
        "Programming Language :: Python",
      ],
      keywords='Zope tracker issue bug',
      author='Peter Bengtsson',
      author_email='mail@peterbe.com',
      url='https://github.com/sureshvv/IsssueTrackerProduct',
      license='GPL',
      packages=['IssueTrackerProduct',
                'IssueTrackerMassContainer',
                'IssueTrackerOpenID',
               ],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        'setuptools',
      ],
)
