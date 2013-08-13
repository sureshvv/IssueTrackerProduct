#!/bin/sh

update_setup() {
  v1=`grep '^version' $1 | awk -F. '{print $NF}' | sed -e 's/dev//' -e "s/'//"`
  v2=`expr $v1 + 1`
  sed -i.bak -e "/version/s/dev$v1/dev$v2/" $1
}

update_setup setup.py
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
