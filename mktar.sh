#!/bin/sh

tar --exclude-vcs \
--exclude=tags \
--exclude=*.pyc \
-zcvf ../IssueTrackerProduct.tgz \
IssueTrackerProduct \
IssueTrackerMassContainer \
IssueTrackerOpenID \
docs \
MANIFEST.in \
README.txt \
setup.py
scp ../IssueTrackerProduct.tgz $SS1:
rm -f $HOME/.cache/pip/*IssueTrackerProduct.tgz*
