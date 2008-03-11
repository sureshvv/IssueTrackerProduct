# -*- coding: iso-8859-1 -*
##
## <peter@fry-it.com>
##

import unittest

import sys, os
import stat
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Globals import SOFTWARE_HOME    
from Testing import ZopeTestCase
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager

import Acquisition

ZopeTestCase.installProduct('MailHost')
ZopeTestCase.installProduct('ZCatalog')
ZopeTestCase.installProduct('ZCTextIndex')
ZopeTestCase.installProduct('SiteErrorLog')
ZopeTestCase.installProduct('PythonScripts')
ZopeTestCase.installProduct('IssueTrackerProduct')

#from Products.IssueTrackerProduct.Permissions import IssueTrackerManagerRole, IssueTrackerUserRole
#from Products.IssueTrackerProduct.Constants import ISSUEUSERFOLDER_METATYPE


#------------------------------------------------------------------------------
#
# Some constants
#

#------------------------------------------------------------------------------

# Open ZODB connection
app = ZopeTestCase.app()
        
# Set up sessioning objects
ZopeTestCase.utils.setupCoreSessions(app)
        
# Set up example applications
#if not hasattr(app, 'Examples'):
#    ZopeTestCase.utils.importObjectFromFile(app, examples_path)
        
# Close ZODB connection
ZopeTestCase.close(app)

#------------------------------------------------------------------------------
pre_submitissue_script_src = """
## Script (Python) "pre_SubmitIssue"
##parameters=
##title=
##
request = context.REQUEST
title = request.get('title',u'')
if title.lower().startswith(u'a'):
    return {'title':u'Subject line must NOT start with an A'}
"""


post_submitissue_script_src = """
## Script (Python) "post_SubmitIssue"
##parameters=issue
##title=
##

if 'Security' in issue.getSections():
   # increase the urgency by one notch

   urgency = issue.getUrgency()

   options = issue.getUrgencyOptions() # acquired 

   try:
       urgency = options[options.index(urgency)+1]
   except IndexError:
       # was already at the topmost
       return
   issue.editIssueDetails(urgency=urgency)
   
"""
    

#------------------------------------------------------------------------------

class TestBase(ZopeTestCase.ZopeTestCase):

    def dummy_redirect(self, *a, **kw):
        self.has_redirected = a[0]
        if kw:
            print "*** Redirecting to %r + (%s)" % (a[0], kw)
        else:
            print "*** Redirecting to %r" % a[0]
    
    def afterSetUp(self):
        # install an issue tracker
        dispatcher = self.folder.manage_addProduct['IssueTrackerProduct']
        dispatcher.manage_addIssueTracker('tracker', 'Issue Tracker')
        
        # install an error_log
        dispatcher = self.folder.manage_addProduct['SiteErrorLog']
        dispatcher.manage_addErrorLog()
        
        
        # if you set this override you won't be able to do a transaction.get().commit()
        # in the unit tests.
        #self.mexpenses.http_redirect = self.dummy_redirect 
        
        request = self.app.REQUEST
        sdm = self.app.session_data_manager
        request.set('SESSION', sdm.getSessionData())
        
        #self.has_redirected = False
        
    def tearDown(self):
        pass


class POP3TestCase(TestBase):
    """ 
    Test to create a POP3 account object and several accepting email accounts
    inside it.
    """ 
    
    def test_creatingAccount(self):
        """ test to create a POP3 account """
        tracker = self.folder.tracker
        
        self.assertEqual(tracker.getPOP3Accounts(), [])
        
        tracker.createPOP3Account('mail.example.com', 'peter', 'secret')
        self.assertEqual(len(tracker.getPOP3Accounts()), 1)
        
        account = tracker.getPOP3Accounts()[0]
        self.assertEqual(account.getTitle(), 'mail.example.com')
        self.assertEqual(account.getHostname(), 'mail.example.com')
        self.assertEqual(account.getPort(), 110)
        self.assertEqual(account.getUsername(), 'peter')
        self.assertFalse(account.doDeleteAfter())
        self.assertFalse(account.doSSL())
        
        self.assertEqual(len(account.getAcceptingEmails()), 0)
        
        # try editing it
        account.manage_editAccount(hostname='m.example.com', username='peterbe', 
                            portnr=210, delete_after=1)
                            
        self.assertEqual(account.getHostname(), 'm.example.com')
        self.assertEqual(account.getPort(), 210)
        self.assertEqual(account.getUsername(), 'peterbe')
        self.assertTrue(account.doDeleteAfter())
    

    def test_creatingAcceptingEmail(self):
        """ test to create a POP3 account accepting email object """
        tracker = self.folder.tracker
        account = tracker.createPOP3Account('mail.example.com', 'peter', 'secret')
        
        # there are unfortunately two different ways to create accepting email
        # objects. Either directly on the account or via the issuetracker 
        # itself. With the latter option, you have to pass the ID of the 
        # account.
        # The latter one is more user friendly and easier to "access" because
        # that's what the DTML files do.
        ae = tracker.createAcceptingEmail(account.getId(), 'mail@example.com')
        self.assertEqual(ae.aq_parent.absolute_url(), account.absolute_url())
        
        self.assertEqual(ae.getEmailAddress(), 'mail@example.com')
        self.assertFalse(ae.doSendConfirm())
        self.assertFalse(ae.revealIssueURL())
        
        ## try to mess with it
        # invalid email address
        self.assertRaises(ValueError, tracker.createAcceptingEmail, account.getId(), 'mail @ example.com')
        # non-existant pop3 account
        self.assertRaises(AttributeError, tracker.createAcceptingEmail, 'zxy', 'mail@example.com')
        
        ## test to edit the accepting email object
        ae.editDetails(email_address='www@example.com', send_confirm=True, reveal_issue_url=True)
        self.assertEqual(ae.getEmailAddress(), 'www@example.com')
        self.assertTrue(ae.doSendConfirm())
        self.assertTrue(ae.revealIssueURL())
        
    def test_acceptingEmailMatch(self):
        """ try creating a accepting email address and add some whitelist and blacklist 
        email addresses. """
        
        tracker = self.folder.tracker
        account = tracker.createPOP3Account('mail.example.com', 'peter', 'secret')
        
        ae = tracker.createAcceptingEmail(account.getId(), 'mail@example.com')
        
        # just blacklist
        ae.editDetails(blacklist_emails=['test@peterbe.com'])
        
        self.assertFalse(ae.acceptOriginatorEmail('TEST@peterbe.COM'))
        self.assertTrue(ae.acceptOriginatorEmail('TEST.ElSE@peterbe.COM'))
        
        ae.editDetails(blacklist_emails=['*@peterbe.com'], whitelist_emails=['exception@peterbe.com'])
        
        self.assertFalse(ae.acceptOriginatorEmail('TEST@peterbe.COM'))
        self.assertTrue(ae.acceptOriginatorEmail('eXception@peterbe.COM'))        
        
                 
        
        
from poplib import POP3, error_proto

class FakePOP3(POP3):
    
    username = 'test'
    password = 'test'
    files = []

    def __init__(self, hostname, port=110):
        
        #for file in files:
        #    assert os.path.isfile(file), "%s does not exist" % file
        self.hostname = hostname
        self.port = port
            
        #self.username = username
        #self.password = password

    def getwelcome(self):
        return "Welcome to fake account"

    def user(self, user):
        if user != self.username:
            raise error_proto("Wrong username.")

    def pass_(self, pswd):
        if pswd != self.password:
            raise error_proto("Wrong password.")

    def list(self, which=None):
        # eg. ('+OK 4 messages:', ['1 71017', '2 2201', '3 7723', '4 44152'], 34)
        files = self.files
        responses = []
        for i, f in enumerate(files):
            responses.append('%s %s' % (i+1, os.stat(f)[stat.ST_SIZE]))
        return ('+OK %s messages:' % len(files), responses, None)

    def retr(self, which):
        # ['response', ['line', ...], octets]
        filename = self.files[which-1]
        return ('response', open(filename, 'r').xreadlines(), None)

    def quit(self):
        pass
        

class EmailInTestCase(TestBase):
    """
    Here we'll try to actually send some emails in to the issuetracker by
    setting up a fake POP3 server. 
    """
    
    def test_emailIn1(self):
        """ test something """
        tracker = self.folder.tracker
        u, p = 'test', 'test' # doesn't really matter
        account = tracker.createPOP3Account('mail.example.com', u, p)
        email = 'mail@example.com'
        ae = tracker.createAcceptingEmail(account.getId(), email)
        
        abs_path = lambda x: os.path.join(os.path.dirname(__file__), x)
        FakePOP3.files = [abs_path('email-in-1.email')]
        result = tracker.check4MailIssues(connect_class=FakePOP3, verbose=False)
        self.assertEqual(result, 'Created 1 issue')

        # this should have created an issue 
        self.assertEqual(len(tracker.getIssueObjects()), 1)
        
        
        
        
        
        
        
def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(POP3TestCase))
    suite.addTest(makeSuite(EmailInTestCase))
    return suite
    
if __name__ == '__main__':
    framework()
        

