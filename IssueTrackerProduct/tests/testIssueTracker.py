# -*- coding: iso-8859-1 -*
##
## <peter@fry-it.com>
##

import unittest
import re
from pprint import pprint
from time import time
from random import randint

import sys, os
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager, noSecurityManager
from DateTime import DateTime
from zExceptions import Unauthorized
import Acquisition

#from base import TestBase, snatched_emails
import base
#ZopeTestCase.installProduct('MailHost')
#ZopeTestCase.installProduct('ZCatalog')
#ZopeTestCase.installProduct('ZCTextIndex')
#ZopeTestCase.installProduct('SiteErrorLog')
#ZopeTestCase.installProduct('PythonScripts')
#ZopeTestCase.installProduct('IssueTrackerProduct')

from IssueTrackerProduct.Permissions import IssueTrackerManagerRole, IssueTrackerUserRole
from IssueTrackerProduct.Constants import ISSUEUSERFOLDER_METATYPE, \
 DEBUG, ISSUE_DRAFT_METATYPE, TEMPFOLDER_REQUEST_KEY, \
 FILTERVALUEFOLDER_THRESHOLD_CLEANING, FILTEROPTION_METATYPE
from IssueTrackerProduct.Errors import DataSubmitError, UserSubmitError

#------------------------------------------------------------------------------
#
# Some constants
#

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

class NewFileUpload:
    def __init__(self, file_path):
        self.file = open(file_path)
        self.filename = os.path.basename(file_path)
        self.file_path = file_path

    def read(self, bytes=None):
        if bytes:
            return self.file.read(bytes)
        else:
            return self.file.read()

    def seek(self, bytes, mode=0):
        self.file.seek(bytes, mode)

    def tell(self):
        return self.file.tell()

class DodgyNewFileUpload:
    """ a file upload that returns a blank string no when you read it """

    def __init__(self, file_path):
        self.file = open(file_path)
        self.filename = os.path.basename(file_path)
        self.file_path = file_path

    def read(self, bytes=None, mode=0):
        return ""

    def seek(self, bytes, mode=0):
        return self.file.seek(bytes, mode)


from IssueTrackerProduct.IssueTracker import FilterValuer

#------------------------------------------------------------------------------

class TestBasex(ZopeTestCase.ZopeTestCase):

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
        #dispatcher = self.folder.manage_addProduct['SiteErrorLog']
        #dispatcher.manage_addErrorLog()

        # install a MailHost
        if not DEBUG:
            dispatcher = self.folder.manage_addProduct['MailHost']
            dispatcher.manage_addMailHost('MailHost')

        # if you set this override you won't be able to do a transaction.get().commit()
        # in the unit tests.
        #self.mexpenses.http_redirect = self.dummy_redirect

        request = self.app.REQUEST
        sdm = self.app.session_data_manager
        request.set('SESSION', sdm.getSessionData())

        #self.has_redirected = False

    def set_cookie(self, key, value, expires=365, path='/',
                   across_domain_cookie_=False,
                   **kw):

        self.app.REQUEST.cookies[key] = value

    #def afterClear(self):
    #    global __trapped_emails__
    #    __trapped_emails__ = []


try:
    from zope import traversing, component, interface
except ImportError:
    traversing = None
    TestFunctionalBase = None

if traversing:

    from zope.traversing.adapters import DefaultTraversable
    from zope.traversing.interfaces import ITraversable
    from zope.component import provideAdapter
    from zope import interface
    from zope.interface import implements

    class TestFunctionalBase(ZopeTestCase.FunctionalTestCase, base.TestBase):

        def afterSetUp(self):
            # install an issue tracker
            dispatcher = self.folder.manage_addProduct['IssueTrackerProduct']
            dispatcher.manage_addIssueTracker('tracker', 'Issue Tracker')

            # install a MailHost
            if not DEBUG:
                dispatcher = self.folder.manage_addProduct['MailHost']
                dispatcher.manage_addMailHost('MailHost')

            request = self.app.REQUEST
            sdm = self.app.session_data_manager
            request.set('SESSION', sdm.getSessionData())

        def beforeSetUp(self):
            super(ZopeTestCase.FunctionalTestCase, self).beforeSetUp()
            component.provideAdapter( \
                        traversing.adapters.DefaultTraversable, (interface.Interface,),ITraversable)



class IssueTrackerTestCase(base.TestBase):

    try:
        # For zope 2.10+ to make it shut up about
        from zope.interface import implements
        from zope.traversing.interfaces import ITraversable
        from zope.traversing.adapters import DefaultTraversable
        from zope import interface
        from zope.component import provideAdapter
        implements(ITraversable)
        provideAdapter(DefaultTraversable,
                       (interface.Interface,),ITraversable)
    except ImportError:
        pass

    def test_addingIssue(self):
        """ test something """
        #self.tracker = self.folder['mexpenses']
        tracker = self.folder.tracker

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)


    def test_modifyingIssue(self):
        """ test something """
        #self.tracker = self.folder['mexpenses']
        tracker = self.folder.tracker

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        request.set('comment', u'COMMENT')
        issue.ModifyIssue(request)

        self.assertEqual(len(issue.getThreadObjects()), 1)


    def test_debatingIssue(self):
        """ test posting a followup under a different email address than the original """
        tracker = self.folder.tracker
        tracker.sitemaster_email = 'something@valid.com'

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        request.set('comment', u'COMMENT')
        request.set('fromname', u'Someone Else')
        request.set('email', u'else@address.com')
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # there should now be a notifiation object
        self.assertEqual(len(issue.getCreatedNotifications()), 1)

        # have a look at that notification object
        notification = issue.getCreatedNotifications()[0]
        self.assertEqual(notification.getTitle(), u'TITLE')
        self.assertTrue(isinstance(notification.getTitle(), unicode))
        self.assertEqual(notification.getIssueID(), issue.getId())
        self.assertEqual(notification.getEmails(), [u'email@address.com'])
        if tracker.doDispatchOnSubmit():
            self.assertTrue(notification.isDispatched())

        # we should now expect an email to have been sent to email@address.com
        assert base.snatched_emails, "not trapped emails"
        latest_email = base.snatched_emails[-1]
        self.assertTrue(latest_email['to'].find('email@address.com') > -1)
        self.assertTrue(latest_email['fr'].find('something@valid.com') > -1)


    def test_debatingIssue_withSmartAvoidanceOfNotifications(self):
        """ If A posts an issue, B follows up and shortly there after A
        follows up too, then if the automatic dispatcher is switched off,
        the notification to A can be ignored since A has already seen the
        followup.
        """
        tracker = self.folder.tracker

        # Important
        tracker.dispatch_on_submit = False

        A = u'email@address.com'
        Af = u'From name'

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', Af)
        request.set('email', A)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        tracker.SubmitIssue(request)


        B = u'else@address.com'
        Bf = u'Someone Else'

        issue = tracker.getIssueObjects()[0]
        request.set('comment', u'COMMENT')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # have a look at that notification object
        notification = issue.getCreatedNotifications()[0]
        self.assertFalse(notification.isDispatched())

        # A returns and posts a followup
        request.set('comment', u'REPLY')
        request.set('fromname', Af)
        request.set('email', A)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # Since the second followup done by A must mean that A
        # doesn't need to be notified about the first notification
        # since A has already made a newer followup.
        # However, B's notification should still be there.

        self.assertEqual(len(issue.getCreatedNotifications()), 1)
        notification = issue.getCreatedNotifications()[0]
        # this should be designated to B
        self.assertEqual(notification.getEmails(), [B])

        # Ok, let's do it again.
        # Now, C joins in so that each notification is designated
        # to two people. By adding a followup by A or B, there is
        # no need to send out the notification to A or B.

        C = u'C@email.com'
        Cf = u'Mr. C'

        request.set('comment', u'COMMENT BY C')
        request.set('fromname', Cf)
        request.set('email', C)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # there should now be one new notification designated
        # to A AND B.

        self.assertEqual(len(issue.getCreatedNotifications()), 2)
        # let's look at the latest notification
        notification = issue.getCreatedNotifications(sort=True)[1]
        self.assertEqual(notification.getEmails(), [A, B])

        request.set('comment', u'COMMENT BY B again')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        self.assertEqual(len(issue.getCreatedNotifications()), 2)
        # let's look at the latest notification
        notification = issue.getCreatedNotifications(sort=True)[1]
        self.assertEqual(notification.getEmails(), [A, C])



    def test_debatingIssue_withSmartAvoidanceOfNotifications_part2(self):
        """ same test_debatingIssue_withSmartAvoidanceOfNotifications() but this time
        test what happens if an issue is created with always notify on or
        an issue is assigned to someone. """


        tracker = self.folder.tracker

        # Important
        tracker.dispatch_on_submit = False

        # add an issue user folder
        # Since manage_addIssueUserFolder() needs to add the two extra roles
        # we have to do that first because manage_addIssueUserFolder() isn't
        # allowed to it because it's not a POST request.
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)
        tracker.acl_users.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [],
                                            email="user@test.com",
                                            fullname="User Name")

        # make the always notify of issuetracker be 'user' and A
        A = 'a@a.com'
        Af = 'Aaa'

        checked = []
        for each in (A, 'user'):
            valid, better_spelling = tracker._checkAlwaysNotify(each)
            if valid:
                checked.append(better_spelling)
        tracker.always_notify = checked

        # If someone else now adds an issue, a notification should
        # be made going out to user@test.com adn a@a.com

        B = u'email@address.com'
        Bf = u'From name'

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        # have a look at that notification object
        self.assertEqual(len(issue.getCreatedNotifications()), 1)
        notification = issue.getCreatedNotifications()[0]
        self.assertFalse(notification.isDispatched())
        self.assertEqual(notification.getEmails(), ['a@a.com','user@test.com'])

        # now, if a@a.com follows up on B's new issue, there'll be
        # you can cross off a@a.com from the notification
        # object.
        request.set('comment', u'COMMENT')
        request.set('fromname', Af)
        request.set('email', A)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # there should now be a new notification object where
        # the latest one goes out to the submitter of the issue
        self.assertEqual(len(issue.getCreatedNotifications()), 2)
        latest_notification = issue.getCreatedNotifications(sort=True)[-1]
        self.assertEqual(latest_notification.getEmails(), [B])



    def test_debatingIssue_withSmartAvoidanceOfNotifications_part3(self):
        """ same as test_debatingIssue_withSmartAvoidanceOfNotifications()
        but create an assignment and then later as that assignee,
        participate in the issue and that should cancel the notification
        going out to the assignee.
        """


        tracker = self.folder.tracker

        # Important
        tracker.dispatch_on_submit = False

        # add an issue user folder
        # Since manage_addIssueUserFolder() needs to add the two extra roles
        # we have to do that first because manage_addIssueUserFolder() isn't
        # allowed to it because it's not a POST request.
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)
        tracker.acl_users.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [],
                                            email="user@test.com",
                                            fullname="User Name")

        # switch on issue assignment
        tracker.manage_UseIssueAssignmentToggle()
        self.assertEqual(len(tracker.getAllIssueUsers()), 1)
        assignee_option = tracker.getAllIssueUsers()[0]
        self.assertEqual(assignee_option['user'].getUserName(), 'user')

        # If someone else now adds an issue, a notification should
        # be made going out to user@test.com adn a@a.com

        B = u'email@address.com'
        Bf = u'From name'

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('assignee', tracker.getAllIssueUsers()[0]['identifier'])
        request.form['notify-assignee'] = '1'
        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        # have a look at that notification object
        self.assertEqual(len(issue.getCreatedNotifications()), 1)
        notification = issue.getCreatedNotifications()[0]
        self.assertFalse(notification.isDispatched())
        self.assertEqual(notification.getEmails(), ['user@test.com'])
        self.assertTrue(notification.getAssignmentObject() is not None)
        assignment = notification.getAssignmentObject()
        self.assertEqual(assignment.getEmail(), B) # who added it
        self.assertEqual(assignment.getAssigneeEmail(), "user@test.com") # assigned to

        # log in as this assignee
        uf = tracker.acl_users
        assert uf.meta_type == ISSUEUSERFOLDER_METATYPE
        user = uf.getUserById('user')
        user = user.__of__(uf)
        newSecurityManager(None, user)

        assert getSecurityManager().getUser().getUserName() == 'user'

        # now reply a comment as this logged in user which should
        # evetually nullify the notification going to this assignee

        request.set('comment', u'COMMENT')
        #request.set('fromname', Af)
        #request.set('email', A)
        request.set('notify', 1)
        issue.ModifyIssue(request)

        # there should now be a new notification object where
        # the latest one goes out to the submitter of the issue
        self.assertEqual(len(issue.getCreatedNotifications()), 1)
        latest_notification = issue.getCreatedNotifications()[0]
        self.assertEqual(latest_notification.getEmails(), [B])



    def test_Real0695_bug(self): # in lack of a better name
        """ test that RSS and RDF feeds have the same security protection
        like viewing the issuetracker, the list of issues or an issue. """
        tracker = self.folder.tracker
        request = self.app.REQUEST

        # Adding an issue
        add_issue_html = tracker.AddIssue(request)
        self.assertTrue(add_issue_html.find('Description:') > -1)

        # add an issue so there's something in the ListIssues, and the XML feeds
        A = u'email@address.com'
        Af = u'From name'
        request.set('title', u'TITLE')
        request.set('fromname', Af)
        request.set('email', A)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        tracker.SubmitIssue(request)


        # first of all, viewing these with the current user should be fine.
        #template_list_html = tracker.ListIssues(request)
        template_list_html = tracker.restrictedTraverse('ListIssues')(request)
        # expect it to say "# Issues: 0" since there are no issues added
        self.assertTrue(template_list_html.find('# Issues: 1') > -1)

        # rss.xml
        rss_xml = getattr(tracker, 'rss.xml')()
        self.assertTrue(rss_xml.find('<title><![CDATA[TITLE #001 (Open)]]></title>') > -1)

        # rdf.xml
        rdf_xml = getattr(tracker, 'rdf.xml')()
        self.assertTrue(rdf_xml.find('<title>TITLE (Open)</title>') > -1)

        # Now, let's disallow anonymous access
        msg = tracker.manage_ViewPermissionToggle()
        self.assertEqual(msg, 'View permission disabled for Anonymous')

        # before we log out, let's create a user with the IssueTracker
        # IssueTrackerManagerRole
        self.folder.acl_users.userFolderAddUser("manager", "secret", [IssueTrackerManagerRole], [])
        self.folder.acl_users.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [])

        # Now, if I log out, none of the viewings above should work
        self.logout()
        assert getSecurityManager().getUser().getUserName() == 'Anonymous User'

        self.assertRaises(Unauthorized, tracker.restrictedTraverse, 'ListIssues')
        self.assertRaises(Unauthorized, tracker.restrictedTraverse, 'rss.xml')
        self.assertRaises(Unauthorized, tracker.restrictedTraverse, 'rdf.xml')



    def test_preSubmitIssue_hook(self):
        """ test adding an issue with a script hook called 'pre_SubmitIssue()' """
        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout

        adder = tracker.manage_addProduct['PythonScripts'].manage_addPythonScript
        adder('pre_SubmitIssue')
        script = getattr(tracker, 'pre_SubmitIssue')
        script.write(pre_submitissue_script_src)

        # With this hook it won't be possible to add a issue where
        # the subject line starts with the letter a. (silly, yes)

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 0)

        request.set('title', u'Some TITLE')

        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)



    def test_postSubmitIssue_hook(self):
        """ test adding an issue with a script hook called 'post_SubmitIssue()' """
        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout
        tracker.can_add_new_sections = True

        # add an issue user folder
        # Since manage_addIssueUserFolder() needs to add the two extra roles
        # we have to do that first because manage_addIssueUserFolder() isn't
        # allowed to it because it's not a POST request.
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)
        tracker.acl_users.userFolderAddUser("user", "secret", [IssueTrackerManagerRole,'Manager'], [],
                                            email="user@test.com",
                                            fullname="User Name")


        adder = tracker.manage_addProduct['PythonScripts'].manage_addPythonScript
        adder('post_SubmitIssue')
        script = getattr(tracker, 'post_SubmitIssue')
        script.write(post_submitissue_script_src)

        # With this hook it won't be possible to add a issue where
        # the subject line starts with the letter a. (silly, yes)

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('newsection', 'Security')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        uf = tracker.acl_users
        assert uf.meta_type == ISSUEUSERFOLDER_METATYPE
        user = uf.getUserById('user')
        user = user.__of__(uf)
        newSecurityManager(None, user)

        assert getSecurityManager().getUser().getUserName() == 'user'



    def test_getModifyTimestamp(self):
        """ test issuetracker.getModifyTimestamp() """
        tracker = self.folder.tracker

        # with no issues, the getModifyTimestamp() should be the
        # same as the issuetrackers' bobobase_modification_time()
        self.assertEqual(int(tracker.bobobase_modification_time()),
                         int(tracker.getModifyTimestamp().strip()))

        # if we add an issue, the issuetrackers' getModifyTimestamp()
        # should be that of the last added issue.
        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]
        self.assertEqual(issue.getModifyTimestamp(), tracker.getModifyTimestamp())

    def test_okFileAttachment(self):
        """ try to add an issue with a crap file attachment """
        tracker = self.folder.tracker
        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('fileattachment', NewFileUpload(os.path.abspath(__file__)))

        tracker.SubmitIssue(request)
        issue = tracker.getIssueObjects()[0]
        self.assertEqual(issue.countFileattachments(), 1)

    def test_crapFileAttachment(self):
        """ try to add an issue with a crap file attachment """

        tracker = self.folder.tracker
        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('fileattachment', DodgyNewFileUpload(os.path.abspath(__file__)))

        # this should fail to add an issue
        tracker.SubmitIssue(request)
        self.assertEqual(len(tracker.getIssueObjects()), 0)

        # this time, try to upload it with a file that is empty
        empty_file = os.path.join(os.path.dirname(__file__), 'size0_file.jpg')
        request.set('fileattachment', NewFileUpload(os.path.abspath(empty_file)))

        tracker.SubmitIssue(request)
        self.assertEqual(len(tracker.getIssueObjects()), 0)


    def test_saveIssueDraft(self):
        """ try to add an issue with a crap file attachment """
        tracker = self.folder.tracker
        request = self.app.REQUEST
        title = u'TITLE'; request.set('title', title)
        fromname = u'From name'; request.set('fromname', fromname)
        email = u'email@address.com'; request.set('email', email)
        description = u'DESCRIPTION'; request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('fileattachment', NewFileUpload(os.path.abspath(__file__)))

        tracker.SaveDraftIssue(request)

        # Because getMyIssueDrafts() depends on cookies and cookies don't
        # work in ZopeTestCase :( we have to fake this a bit
        drafts = tracker.getDraftsContainer().objectValues(ISSUE_DRAFT_METATYPE)
        assert len(drafts) == 1

        # Now check that draft
        draft = drafts[0]
        self.assertEqual(draft.getTitle(), title)
        self.assertEqual(draft.getDescription(), description)
        self.assertEqual(draft.getFromname(), fromname)
        self.assertEqual(draft.getEmail(), email)
        self.assertEqual(draft.getType(), tracker.getDefaultType())
        self.assertEqual(draft.getUrgency(), tracker.getDefaultUrgency())

        # from this it will be possible to get the files back via the
        # tempfolder
        assert request.get(TEMPFOLDER_REQUEST_KEY), "no tempfolder set in request"
        tempfolder = tracker._getTempFolder()
        files = tempfolder[request.get(TEMPFOLDER_REQUEST_KEY)].objectValues('File')
        assert files, "no temp files"
        temp_file = files[0]
        self.assertEqual(temp_file.getId(), os.path.basename(__file__))

    def test_searchIssues(self):
        """ basic search tests """
        tracker = self.folder.tracker
        request = self.app.REQUEST
        title = u'titles are working'; request.set('title', title)
        fromname = u'From name'; request.set('fromname', fromname)
        email = u'email@address.com'; request.set('email', email)
        description = u'DESCRIPTION is a in the this test'
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('fileattachment', NewFileUpload(os.path.abspath(__file__)))

        tracker.SubmitIssue(request)
        assert tracker.getIssueObjects()

        issue = tracker.getIssueObjects()[0]

        # search and find it
        q = 'working'
        self.assertEqual(issue, tracker._searchCatalog(q, search_only_on=None)[0])
        self.assertEqual(issue, tracker._searchCatalog(q, search_only_on='title')[0])

        # don't expect to find it
        q = 'notmentioned'
        self.assertEqual(tracker._searchCatalog(q, search_only_on='description'), [])
        self.assertEqual(tracker._searchCatalog(q), [])

        # search fuzzy and find it
        q = 'title'
        self.assertEqual(issue, tracker._searchCatalog(q)[0])
        # it should be case insensitive
        q = 'DeScriPtion'
        self.assertEqual(issue, tracker._searchCatalog(q)[0])

        # low level test of searching by filename
        self.assertEqual(issue, tracker._searchByFilename(os.path.basename(__file__))[0])
        # and do it fuzzy
        self.assertEqual(issue, tracker._searchByFilename(os.path.basename(__file__).upper())[0])
        # or without the extension
        name = os.path.splitext(os.path.basename(__file__))[0]
        self.assertEqual(issue, tracker._searchByFilename(name)[0])

        # Post a followup and expect to be able to search and find it
        request.set('comment', u'COMMENT')
        this_file = os.path.abspath(__file__)
        #a_file = os.listdir(os.path.dirname(this_file))[-1]
        a_file = os.path.join(os.path.dirname(this_file), 'CHANGES.log')
        request.set('fileattachment', NewFileUpload(a_file))
        issue.ModifyIssue(request)
        thread = issue.getThreadObjects()[0]

        # search for the comment
        q = 'COMmenT'
        # and expect to find it's parent object which is the issue
        self.assertEqual(issue, tracker._searchCatalog(q)[0])
        # when finding things by threads it puts this into REQUEST
        self.assertEqual(request.get('FirstThreadResultId'), issue.getId())

        # search for a threads file
        q = os.path.basename(a_file)
        # and expect to find it's parent object which is the issue
        self.assertEqual(issue, tracker._searchCatalog(q)[0])
        # and a variation of that
        q = os.path.splitext(q)[0]
        self.assertEqual(issue, tracker._searchCatalog(q)[0])

        # If you run the UpdateEverything() we can expect the same
        # content in the catalog
        tracker.manage_delObjects(['ICatalog'])
        tracker.UpdateEverything()

        # search for the comment
        q = 'COMmenT'
        # and expect to find it's parent object which is the issue
        self.assertEqual(issue, tracker._searchCatalog(q)[0])
        # when finding things by threads it puts this into REQUEST
        self.assertEqual(request.get('FirstThreadResultId'), issue.getId())
        # search for a threads file
        q = os.path.basename(a_file)
        # and expect to find it's parent object which is the issue
        self.assertEqual(issue, tracker._searchCatalog(q)[0])
        # and a variation of that
        q = os.path.splitext(q)[0]
        self.assertEqual(issue, tracker._searchCatalog(q)[0])

    def test_filterIssues(self):
        """ test to call filter issues and note how the filter should be saved and
        should be reusable later. """

        tracker = self.folder.tracker
        request = self.app.REQUEST

        # first, the user who performs this test is a normal zope acl
        # user. Let's add a name and email so that we can make sure
        # this is information is saved in the saved filter
        self.set_cookie(tracker.getCookiekey('name'), u'Bob')
        self.set_cookie(tracker.getCookiekey('email'), u'bob@test.com')

        # initially there shouldn't be a folder called 'saved-filters'
        self.assertFalse(hasattr(tracker, 'saved-filters'))
        # and there shouldn't be a zcatalog called 'saved-filters-catalog'
        self.assertFalse(hasattr(tracker, 'saved-filters-catalog'))

        # On the homepage, the links to see only say issues "On hold" is
        # /ListIssues?Filterlogic=show&f-statuses=on%20hold
        # Let's mimick that:
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        # this should now have create the saved-filters folder
        # and the saved-filters-catalog
        self.assertTrue(hasattr(tracker, 'saved-filters'))
        self.assertTrue(hasattr(tracker, 'saved-filters-catalog'))

        # let's look at what was created in the saved-filters folder
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)

        # since I'm here logged into Zope as a normal Zope user
        # we can expect to find that the saved filter should be to me
        zopeuser = tracker.getZopeUser()
        path = '/'.join(zopeuser.getPhysicalPath())
        name = zopeuser.getUserName()
        acl_adder = ','.join([path, name])
        saved_filter = saved_filters[0]

        self.assertEqual(saved_filter.acl_adder, acl_adder)
        self.assertEqual(saved_filter.getTitle(), u"Only on hold issues")
        # this is who created the filter (quite unimportant)
        self.assertEqual(saved_filter.adder_fromname, u'Bob')
        self.assertEqual(saved_filter.adder_email, 'bob@test.com')
        # and we didn't need to associate with a cookie key
        self.assertEqual(saved_filter.key, '')

        # the logic was to show
        self.assertEqual(saved_filter.filterlogic, 'show')

        # some attributes are automatically set for the issue metadata
        self.assertEqual(saved_filter.sections, None)
        self.assertEqual(saved_filter.urgencies, None)
        self.assertEqual(saved_filter.types, None)
        self.assertEqual(saved_filter.statuses, [u'on hold'])

        # We should have a saved-filters-catalog created
        catalog = tracker.getFilterValuerCatalog()
        self.assertTrue(catalog is not None)
        # and there should only be one brain it right now
        self.assertTrue(len(catalog.searchResults()) == 1)

        saved_filter_from_brain = catalog.searchResults()[0].getObject()
        self.assertTrue(saved_filter_from_brain == saved_filter)

        # the high level function getMySavedFilters() uses the catalog
        # to extract the saved filters with the most recent one
        # first.
        saved_filter_from_mysavedfilters = tracker.getMySavedFilters()[0]
        self.assertTrue(saved_filter_from_mysavedfilters == saved_filter)


        # If you run ListIssuesFiltered() again, it should have to create
        # one more new saved filter
        tracker.ListIssuesFiltered()

        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)

        # But if we change the parameters a little bit it should have
        # created a new saved filter
        request.set('f-statuses','taken')
        tracker.ListIssuesFiltered()
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 2)

        # getMySavedFilters() is smart in that it returns the filters ordered.
        # Test that the more recent one comes first
        saved_filters_from_mysavedfilters = tracker.getMySavedFilters()
        self.assertEqual(saved_filters_from_mysavedfilters[0].statuses, [u'taken'])

        # Test the function getCurrentlyUsedSavedFilter(request_only=True)
        assert tracker.getCurrentlyUsedSavedFilter() is None

        saved_filter_id = tracker.getCurrentlyUsedSavedFilter(request_only=False)
        # now check that this is the correct one
        self.assertEqual(saved_filter_id, saved_filters_from_mysavedfilters[0].getId())
        # another (more long winded) way of checking this is by that since the
        # last filter was to filter by "taken". Check that this is what the
        # filter does that comes from getCurrentlyUsedSavedFilter(request_only=False)
        current_saved_filter = getattr(getattr(tracker, 'saved-filters'), saved_filter_id)
        self.assertEqual(current_saved_filter.statuses, [u'taken'])


        # Some options that can be passed directly to _ListIssuesFiltered
        # are:
        #   skip_filter
        #   skip_sort
        #
        # To set these for ListIssuesFiltered() you have to put them in the
        # REQUEST. These are useful if you for example want to ignore possibly
        # filters in session such as for the homepage where it uses
        # ListIssuesFiltered() but without any filtering.
        # The skip_sort is useful to set when you don't want any sorting since
        # sorting will only cost time.
        # XXX: Only able to test this WITH issues


    def test_filterIssues_anonymous_user(self):
        """ test filtering issues when the user is not logged in """
        # when *not* logged in there are two ways to remember a saved filter:
        #   by name and email
        #   by a cookie key
        # Let's first try to filter issues as a complete nobody

        noSecurityManager()
        tracker = self.folder.tracker
        request = self.app.REQUEST

        tracker.set_cookie = self.set_cookie

        # On the homepage, the links to see only say issues "On hold" is
        # /ListIssues?Filterlogic=show&f-statuses=on%20hold
        # Let's mimick that:
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        # let's look at what was created in the saved-filters folder
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)
        saved_filter = saved_filters[0]
        self.assertTrue(saved_filter.getKey() in request.cookies.values())

        # run it again and it shouldn't create another saved filter
        tracker.ListIssuesFiltered()
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)

    def test_filterIssues_anonymous_named_user(self):
        """ test filtering when the user is no logged in but has a name
        and email in the cookie. """

        noSecurityManager()
        tracker = self.folder.tracker
        request = self.app.REQUEST

        tracker.set_cookie = self.set_cookie

        self.set_cookie(tracker.getCookiekey('name'), u'Bob')
        self.set_cookie(tracker.getCookiekey('email'), u'bob@test.com')

        # On the homepage, the links to see only say issues "On hold" is
        # /ListIssues?Filterlogic=show&f-statuses=on%20hold
        # Let's mimick that:
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        # let's look at what was created in the saved-filters folder
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)
        saved_filter = saved_filters[0]
        self.assertEqual(saved_filter.adder_email, 'bob@test.com')
        self.assertEqual(saved_filter.adder_fromname, u'Bob')

        # run it again and it shouldn't create another saved filter
        tracker.ListIssuesFiltered()
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)


    def test_filterIssues_anonymous_named_user_no_email(self):
        """ test filtering when the user is no logged in but has a name
        and email in the cookie. """

        noSecurityManager()
        tracker = self.folder.tracker
        request = self.app.REQUEST

        tracker.set_cookie = self.set_cookie

        self.set_cookie(tracker.getCookiekey('name'), u'Bob')

        # On the homepage, the links to see only say issues "On hold" is
        # /ListIssues?Filterlogic=show&f-statuses=on%20hold
        # Let's mimick that:
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        # let's look at what was created in the saved-filters folder
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)
        saved_filter = saved_filters[0]
        self.assertEqual(saved_filter.adder_fromname, u'Bob')

        # run it again and it shouldn't create another saved filter
        tracker.ListIssuesFiltered()
        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)


    def test_filterIssues_anonymous_bot(self):
        """ When the http user agent is a bot (Googlebot, msnbot etc.) don't
        save the filter persistently.
        """

        noSecurityManager()
        tracker = self.folder.tracker
        request = self.app.REQUEST


        request.set('HTTP_USER_AGENT',
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")

        # On the homepage, the links to see only say issues "On hold" is
        # /ListIssues?Filterlogic=show&f-statuses=on%20hold
        # Let's mimick that:
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        # there shouldn't even be a folder called 'saved-filters'
        self.assertEqual(getattr(tracker, 'saved-filters', None), None)



    def test_filterIssues_recycleable(self):
        """ test to call filter issues and note how the filter should be saved and
        should be reusable later.
        When you *go back* to run a filter you've already done before it should be
        able to reuse an existing object instead of having to create a new one."""

        tracker = self.folder.tracker
        request = self.app.REQUEST

        # 1
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)

        # 2
        request.set('f-statuses','taken')
        tracker.ListIssuesFiltered()

        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 2)

        # 3
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 2)

    def test_filterIssues_from_cookie_after_purge(self):
        """ If all the saved-filters are deleted and someone has a cookie
        of an old savedfilter, if the saved filter is deleted, getting it
        from the cookie shouldn't raise an AttributeError.
        """

        tracker = self.folder.tracker
        request = self.app.REQUEST

        tracker.set_cookie = self.set_cookie

        ckey = tracker.getCookiekey('remember_savedfilter_persistently')
        tracker.set_cookie(ckey, 1)

        # 1
        request.set('Filterlogic','show')
        request.set('f-statuses','on hold')
        tracker.ListIssuesFiltered()

        self.assertTrue('__issuetracker_savedfilter_id-tracker' in request.cookies)

        saved_filters = getattr(tracker, 'saved-filters').objectValues()
        self.assertEqual(len(saved_filters), 1)

        # now, mess with it
        tracker.manage_delObjects(['saved-filters','saved-filters-catalog'])

        # if the cookie causes an AttributeError, then ListIssuesFiltered()
        # here wouldn't work. Just running this is the final test.
        tracker.ListIssuesFiltered()


    def test_clean_saved_filters(self):
        """ CleanOldSavedFilters() is called by manage_UpdateEverything() but
        also if the number of saved filters exceeds FILTERVALUEFOLDER_THRESHOLD_CLEANING.
        We'll first try the manual way of cleaning.
        """
        tracker = self.folder.tracker

        container = tracker._getFilterValueContainer()
        for i in range(100):
            oid = 'random-%s' % i
            instance = FilterValuer(oid, 'filter name')
            container._setObject(oid, instance)
            valuer = container._getOb(oid)

            if randint(1, 5) == 1:
                valuer.set('acl_adder', 'fake acl adder')
            elif randint(1, 4) == 1:
                valuer.set('key', str(randint(1, 10)))
            else:
                valuer.set('adder_email', 'email')

            valuer.mod_date = DateTime(time() - randint(1000, 1000000)*10)
            valuer.index_object()


        max_ = FILTERVALUEFOLDER_THRESHOLD_CLEANING
        count_filtervaluers = len(container.objectIds())
        assert count_filtervaluers < max_

        # there should also be equally many indexed objects as there
        # are reported by len(objectids)
        catalog = tracker.getFilterValuerCatalog()
        search = {'meta_type': FILTEROPTION_METATYPE}
        brains = catalog.searchResults(**search)
        assert len(brains) == count_filtervaluers

        # there are now 100 old saved filters whose
        # bobobase_modification_time ranges between 4 to 0 months old
        msg = tracker.CleanOldSavedFilters()
        msg_regex = re.compile('Deleted (\d+) old saved filters')
        no_deleted = int(msg_regex.findall(msg)[0])

        self.assertTrue(no_deleted < count_filtervaluers)
        left = count_filtervaluers - no_deleted

        brains = catalog.searchResults(**search)
        assert len(brains) == left, \
        "no. brains=%s, left=%s" %(len(brains), left)



    def test_clean_saved_filters_then_implode(self):
        """ Similar to test_clean_saved_filters() except this time we're
        making sure ALL saved filters are so old that if we send
        implode_if_possible=True to CleanOldSavedFilters() and expect the
        container to disappear.
        """
        tracker = self.folder.tracker
        container = tracker._getFilterValueContainer()
        for i in range(100):
            oid = 'random-%s' % i
            instance = FilterValuer(oid, 'filter name')
            container._setObject(oid, instance)
            valuer = container._getOb(oid)

            if randint(1, 5) == 1:
                valuer.set('acl_adder', 'fake acl adder')
            elif randint(1, 4) == 1:
                valuer.set('key', str(randint(1, 10)))
            else:
                valuer.set('adder_email', 'email')

            valuer.mod_date = DateTime(time() - randint(1000, 10000)*3600)
            valuer.index_object()

        self.assertTrue('saved-filters' in tracker.objectIds())
        msg = tracker.CleanOldSavedFilters(implode_if_possible=True)
        self.assertTrue('saved-filters' not in tracker.objectIds())

        # and the catalog should be empty
        catalog = tracker.getFilterValuerCatalog()
        search = {'meta_type': FILTEROPTION_METATYPE}
        brains = catalog.searchResults(**search)
        self.assertTrue(len(brains) == 0)

    def test_unicode_in_statuses(self):
        """ test that it's possible to set a verb:action pair to the
        statuses that is unicode. """

        tracker = self.folder.tracker
        request = self.app.REQUEST

        for status, verb in tracker.getStatusesMerged(aslist=True):
            self.assertTrue(isinstance(status, unicode))
            self.assertTrue(isinstance(verb, unicode))

        # All the default ones are easy, lets spice it up a bit
        statuses_and_verbs = [u'open, open',
                              u'taken, take',
                              u'on hold, put on hold',
                              u'a pr\xe9c\xe9dente, faire pr\xe9c\xe9dente',
                              u'rejected, reject',
                              u'completed, complete']
        request.set('statuses-and-verbs', statuses_and_verbs)

        tracker.manage_editIssueTrackerProperties(carefulbooleans=True,
                                                  REQUEST=request)

        for status, verb in tracker.getStatusesMerged(aslist=True):
            self.assertTrue(isinstance(status, unicode))
            self.assertTrue(isinstance(verb, unicode))


    def test_changeIssueDetails(self):
        """ when you change issuedetails the changes are record as
        an attribute in the issue. """

        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout
        tracker.can_add_new_sections = True

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 0)

        # pretend to change sections but actually not
        issue.editIssueDetails(sections=issue.getSections(),
                               type=issue.getType(),
                               urgency=issue.getUrgency())
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 0)

        # now actually change something (sections)
        sections_before = issue.getSections()
        issue.editIssueDetails(sections=['Foo'])
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1)
        change = changes[-1]
        self.assertEqual(change['sections']['old'], sections_before)
        self.assertEqual(change['sections']['new'], ['Foo'])
        self.assertTrue('change_date' in change)
        self.assertTrue(hasattr(change['change_date'], 'strftime'))

        # now actually change something (type)
        type_before = issue.getType()
        issue.editIssueDetails(type='feature request')
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1) # merged with the previous one
        change = changes[-1]
        self.assertEqual(change['type']['old'], type_before)
        self.assertEqual(change['type']['new'], 'feature request')


        # change several things
        urgency_before = issue.getUrgency()
        confidential_before = issue.isConfidential()
        url2issue_before = issue.getURL2Issue()
        tracker.use_estimated_time = True
        tracker.use_actual_time = True
        estimated_time_hours_before = issue.getEstimatedTimeHours()
        actual_time_hours_before = issue.getActualTimeHours()

        issue.editIssueDetails(urgency='low',
                               confidential=not confidential_before,
                               url2issue='http://www.issuetrackerproduct.com',
                               estimated_time_hours=1,
                               actual_time_hours=2
                               )
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1) # merged with the previous two

        change = changes[-1]
        self.assertEqual(change['acl_adder'], '/test_folder_1_/acl_users,test_user_1_')\


    def test_changeIssueDetails_twice_merged(self):
        """ if you change details of an issue twice within the same minute,
        merge the changes into one change to prevent the interface from looking
        like this:
            Today 12:16 by Peter
               Size: 5 6
            Today 12:16 by Peter
               Age: 28 29
        """
        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout
        tracker.can_add_new_sections = True

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        # now actually change something (sections)
        sections_before = issue.getSections()
        issue.editIssueDetails(sections=['Foo'])
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1)
        change = changes[-1]
        self.assertEqual(change['sections']['old'], sections_before)
        self.assertEqual(change['sections']['new'], ['Foo'])
        self.assertTrue('change_date' in change)
        self.assertTrue(hasattr(change['change_date'], 'strftime'))

        # change the urgency too as a separate request
        issue.editIssueDetails(urgency='high')
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1)

    def test_changeIssueDetails_twice_void(self):
        """ if you change details of an issue twice within the same minute,
        merge the changes into one change to prevent the interface from looking
        like this:
            Today 12:16 by Peter
               Size: 5 6
            Today 12:16 by Peter
               Age: 6 5

        But if the change, within one minute, goes back to the same value
        as before, drop the change altogether.
        """
        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout
        tracker.can_add_new_sections = True

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        # now actually change something (sections)
        sections_before = issue.getSections()
        issue.editIssueDetails(sections=['Foo'])
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 1)
        change = changes[-1]
        self.assertEqual(change['sections']['old'], sections_before)
        self.assertEqual(change['sections']['new'], ['Foo'])
        self.assertTrue('change_date' in change)
        self.assertTrue(hasattr(change['change_date'], 'strftime'))

        # change the urgency too as a separate request
        issue.editIssueDetails(sections=sections_before)
        changes = issue.getDetailChanges()
        self.assertEqual(len(changes), 0)


    def test_cataloging_issues(self):
        """ adding an issue and threads to that should be indexed in the
        ICatalog correctly.
        If you do an UpdateEverything they should still be there.
        """
        tracker = self.folder.tracker
        tracker.dispatch_on_submit = False # no annoying emails on stdout
        tracker.can_add_new_sections = True

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]

        request.set('comment', u'COMMENT')
        issue.ModifyIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)
        self.assertEqual(len(issue.getThreadObjects()), 1)

        # lets check what's in the catalog
        catalog = tracker.getCatalog()
        # seaching inside it for path '/' should find two brains
        brains = catalog.searchResults(path='/')
        self.assertEqual(len(brains), 2)
        meta_types = [x.meta_type for x in brains]
        self.assertTrue('Issue Tracker Issue Thread' in meta_types)
        self.assertTrue('Issue Tracker Issue' in meta_types)

        # If we run UpdateEverything, the same content is expected in the
        # catalog
        tracker.UpdateEverything()
        brains = catalog.searchResults(path='/')
        self.assertEqual(len(brains), 2)
        meta_types = [x.meta_type for x in brains]
        self.assertTrue('Issue Tracker Issue Thread' in meta_types)
        self.assertTrue('Issue Tracker Issue' in meta_types)

    def test_assign_on_submit_email(self):
        """ Make sure the issue title is in the subjectline when you assign an issue to
        someone """
        tracker = self.folder.tracker
        # set a valid sitemaster email address
        tracker.sitemaster_email = 'peter@test.com'
        # switch on assignment
        tracker.use_issue_assignment = True
        # add a user to assign stuff to
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)
        tracker.acl_users.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [],
                                            email="user@test.com",
                                            fullname="User Name")
        user = tracker.getAllIssueUsers()[0]

        request = self.app.REQUEST
        request.set('title', u'A TITLE')
        request.set('fromname', u'From name')
        request.set('email', u'email@address.com')
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('assignee', user['identifier'])
        request.form['notify-assignee'] = '1'

        no_trapped_emails = len(base.snatched_emails)
        tracker.SubmitIssue(request)

        # There should now be one issue...
        issues = tracker.getIssueObjects()
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        # and it should have an assignment
        assignments = issue.getAssignments()
        self.assertEqual(len(assignments), 1)
        assignment = assignments[0]

        self.assertEqual(assignment.getFromname(), request.get('fromname'))
        self.assertEqual(assignment.getEmail(), request.get('email'))

        self.assertEqual(assignment.getAssigneeFullname(), u"User Name")
        self.assertEqual(assignment.getAssigneeEmail(), "user@test.com")

        # Look at the notifications inside the issue
        notifications = issue.getCreatedNotifications()
        self.assertEqual(len(notifications), 1)
        notification = notifications[0]

        assert len(base.snatched_emails) == no_trapped_emails + 1

        # check that the
        assert notification.dispatched

        latest_email = base.snatched_emails[-1]

        self.assertTrue(latest_email['subject'].count(request.get('title')))

        # then, later change the assignment and that should trigger another
        # email notifications
        tracker.acl_users.userFolderAddUser("user2", "secret", [IssueTrackerUserRole], [],
                                            email="user2@test.com",
                                            fullname="Second Name")
        users = tracker.getAllIssueUsers()
        user2 = [x for x in users if x['identifier'].endswith('user2')][0]

        uf = tracker.acl_users
        user = uf.getUserById('user')
        user = user.__of__(uf)
        newSecurityManager(None, user)

        assert getSecurityManager().getUser().getUserName() == 'user'

        issue.changeAssignment(user2['identifier'], send_email=True)

        # No email will be sent to the doer????
        assert len(base.snatched_emails) == no_trapped_emails + 1

        assignments = issue.getAssignments()

        # No assignment gets added???
        self.assertEqual(len(assignments), 1)

        # Look at the notifications inside the issue
        notifications = issue.getCreatedNotifications()

        # No notification gets added???
        self.assertEqual(len(notifications), 1)

        notification = notifications[-1]
        assert notification.dispatched

        latest_email = base.snatched_emails[-1]

        self.assertTrue(latest_email['subject'].count(request.get('title')))
        self.assertTrue(latest_email['to'], 'user2@test.com')


    def test_showStrftimeFriendly(self):
        """test the base script showStrftimeFriendly()"""
        tracker = self.folder.tracker
        func = tracker.showStrftimeFriendly

        tests = [('%d/%m %Y', 'DD/MM YYYY'),
                 ('%d/%m %Y %H:%M', 'DD/MM YYYY hh:mm'),
                 ('%d %B %Y', 'DD month YYYY'),
                 ('%d %B %Y %H:%M', 'DD month YYYY hh:mm'),
                 ]

        for input_, output in tests:
            self.assertEqual(func(input_), output)

        tests = [('%d/%m %Y', 'DD/MM YYYY'),
                 ('%d/%m %Y %H:%M', 'DD/MM YYYY'),
                 ('%d %B %Y', 'DD month YYYY'),
                 ('%d %B %Y %H:%M', 'DD month YYYY'),
                 ]

        for input_, output in tests:
            self.assertEqual(func(input_, strip_hour_part=True),
                             output)

    def test_getDueDateCSSSelector(self):
        """return some suitable CSS selectors based on the due date"""
        tracker = self.folder.tracker
        func = tracker.getDueDateCSSSelector

        # feed it a date in the past and it will return 'dd-past'
        past = DateTime('2009/01/01')
        self.assertEqual(func(past), 'dd-past')
        # as a string
        self.assertEqual(func('2009/01/01'), 'dd-past')

        today = DateTime(DateTime().strftime('%Y/%m/%d'))
        self.assertEqual(func(today), 'dd-today')
        # as a string
        self.assertEqual(func(DateTime().strftime('%Y/%m/%d')), 'dd-today')

        tomorrow = DateTime(DateTime().strftime('%Y/%m/%d')) + 1
        self.assertEqual(func(tomorrow), 'dd-tomorrow')
        # as a string
        self.assertEqual(func((DateTime()+1).strftime('%Y/%m/%d')), 'dd-tomorrow')

        future = DateTime(DateTime().strftime('%Y/%m/%d')) + 100
        self.assertEqual(func(future), 'dd-future')
        # as a string
        self.assertEqual(func((DateTime()+100).strftime('%Y/%m/%d')), 'dd-future')

        # junk
        self.assertEqual(func('xajsd'), '')
        self.assertEqual(func(1230), '')


    def test_submitting_with_due_date(self):
        """submit an issue with a due date"""

        title = u"Title"
        description = u"Description"

        tracker = self.folder.tracker
        request = self.app.REQUEST
        request.set('title', title)
        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('due_date', '2010/01/01')

        tracker.SubmitIssue(request)

        # it should be possible to display it
        issue = tracker.getIssueObjects()[0]
        # because due dates aren't enabled yet
        self.assertEqual(issue.getDueDate(), None)

        tracker.enable_due_date = True

        title = u"Somethjing"
        description = u"Different"

        request.set('title', title)
        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('due_date', '2010/01/01')

        tracker.SubmitIssue(request)
        #issue = [x for x in tracker.getIssueObjects() if x.title==title][0]
        issue = tracker.getIssueObjects()[-1]
        self.assertEqual(issue.getDueDate(), DateTime('2010/01/01'))

        # But just because you've enabled it doesn't necessarily mean
        # you have to set it every time
        title = u"Entirely"
        description = u"Different"

        request.set('title', title)
        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('due_date', '')

        tracker.SubmitIssue(request)
        issue = tracker.getIssueObjects()[-1]
        self.assertEqual(issue.getDueDate(), None)

    def test_editing_due_date(self):
        """test changing date"""
        tracker = self.folder.tracker
        tracker.enable_due_date = True

        title = u"Title"
        description = u"Description"

        request = self.app.REQUEST
        request.set('title', title)
        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('due_date', '2010/01/01')

        tracker.SubmitIssue(request)

        # it should be possible to display it
        issue = tracker.getIssueObjects()[0]
        #pprint(list(issue.detail_changes))
        assert not issue.detail_changes
        self.assertEqual(issue.getDueDate(), DateTime('2010/01/01'))

        issue.editIssueDetails(due_date='2010/02/02')
        # there should now be one item in the issue.detail_changes
        assert len(issue.detail_changes) == 1
        change = issue.detail_changes[0]
        # it should have a key called 'due_date'
        assert change['due_date']
        self.assertEqual(change['due_date']['old'], DateTime('2010/01/01'))
        self.assertEqual(change['due_date']['new'], DateTime('2010/02/02'))

        self.assertEqual(issue.getDueDate(), DateTime('2010/02/02'))

        issue.editIssueDetails(due_date='')
        self.assertEqual(issue.getDueDate(), None)

        issue.editIssueDetails(due_date='2010/03/03')
        self.assertEqual(issue.getDueDate(), DateTime('2010/03/03'))


    def test_submitting_bad_due_dates(self):
        """test setting faux due dates"""
        tracker = self.folder.tracker

        title = u"Title"
        description = u"Description"

        tracker.enable_due_date = True

        request = self.app.REQUEST
        request.set('title', title)
        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('due_date', 'xxx')

        html = tracker.SubmitIssue(request)
        self.assertTrue(html.count('<span class="submiterror">Invalid date</span>'))

        # only 28 days in feb
        request.set('due_date', '2009/02/29')
        html = tracker.SubmitIssue(request)
        self.assertTrue(html.count('<span class="submiterror">Invalid date</span>'))

        assert not list(tracker.getIssueObjects())

    def test_parseDueDate(self):
        """parseDueDate() takes a date string and returns a date object or None"""

        tracker = self.folder.tracker
        func = tracker.parseDueDate

        self.assertEqual(func('2009/01/01'), DateTime('2009/01/01'))
        self.assertEqual(func('13 april 2009'), DateTime('13 april 2009'))
        self.assertEqual(func('today'),
                         DateTime(DateTime().strftime('%Y/%m/%d')))
        self.assertEqual(func('tomorrow'),
                         DateTime((DateTime()+1).strftime('%Y/%m/%d')))

        self.assertEqual(func('junk'), None)
        self.assertEqual(func('2009/02/29'), None)
        # but 2008 was a leap year
        self.assertEqual(func('2008/02/29'), DateTime('2008/02/29'))


    def test_filter_by_due_date(self):
        """test to list issues with a filter"""
        tracker = self.folder.tracker

        title = u"Title"
        description = u"Description"

        tracker.enable_due_date = True
        def hourless(d):
            return DateTime(d.strftime('%Y/%m/%d'))

        today = hourless(DateTime())
        yesterday = hourless(DateTime()-1)
        tomorrow = hourless(DateTime()+1)
        future = hourless(DateTime()+7)

        title_no_due_date = 'NO DUE DATE'
        title_today = 'TODAY'
        title_yesterday = 'YESTERDAY'
        title_tomorrow = 'TOMORROW'
        title_future = 'FUTURE'

        request = self.app.REQUEST

        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        request.set('title', title_no_due_date)
        request.set('due_date', '')
        html = tracker.SubmitIssue(request)

        request.set('title', title_today)
        request.set('due_date', today)
        html = tracker.SubmitIssue(request)

        request.set('title', title_yesterday)
        request.set('due_date', yesterday)
        html = tracker.SubmitIssue(request)

        request.set('title', title_tomorrow)
        request.set('due_date', tomorrow)
        html = tracker.SubmitIssue(request)

        request.set('title', title_future)
        request.set('due_date', future)
        html = tracker.SubmitIssue(request)

        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 5)


        request.set('Filterlogic', 'block')
        request.set('filteroptions', 1)

        request.set('f-due', '')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 5)

        request.set('f-due', 'FutUrE') # case insensitive
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 4)
        self.assertTrue(title_future not in [x.title for x in seq])

        request.set('f-due', 'Overdue')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 4)
        self.assertTrue(title_yesterday not in [x.title for x in seq])

        request.set('f-due', 'Today')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 4)
        self.assertTrue(title_today not in [x.title for x in seq])

        request.set('f-due', 'TomorroW')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 4)
        self.assertTrue(title_tomorrow not in [x.title for x in seq])

        # combos
        request.set('f-due', ['FutUrE','Today'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 3)
        self.assertTrue(title_future not in [x.title for x in seq])
        self.assertTrue(title_today not in [x.title for x in seq])

        request.set('f-due', ['Overdue','Today'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 3)
        self.assertTrue(title_yesterday not in [x.title for x in seq])
        self.assertTrue(title_today not in [x.title for x in seq])

        request.set('f-due', ['FutUrE','OverDUE'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 3)
        self.assertTrue(title_future not in [x.title for x in seq])
        self.assertTrue(title_yesterday not in [x.title for x in seq])


        # Change the filter logic
        request.set('Filterlogic', 'show')

        request.set('f-due', '')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 5)

        request.set('f-due', 'TODAy')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 1)
        self.assertTrue(title_today in [x.title for x in seq])

        request.set('f-due', 'OVERdue')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 1)
        self.assertTrue(title_yesterday in [x.title for x in seq])

        request.set('f-due', 'tomorrow')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 1)
        self.assertTrue(title_tomorrow in [x.title for x in seq])

        request.set('f-due', 'futurE')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 1)
        self.assertTrue(title_future in [x.title for x in seq])

        # combos
        request.set('f-due', ['tomorrow','future'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 2)
        self.assertTrue(title_tomorrow in [x.title for x in seq])
        self.assertTrue(title_future in [x.title for x in seq])

        request.set('f-due', ['overdue','future'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 2)
        self.assertTrue(title_yesterday in [x.title for x in seq])
        self.assertTrue(title_future in [x.title for x in seq])

        request.set('f-due', ['overdue','today'])
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 2)
        self.assertTrue(title_yesterday in [x.title for x in seq])
        self.assertTrue(title_today in [x.title for x in seq])


    def test_sort_by_due_date(self):
        """test to sort issues by due date"""
        tracker = self.folder.tracker

        title = u"Title"
        description = u"Description"

        tracker.enable_due_date = True
        def hourless(d):
            return DateTime(d.strftime('%Y/%m/%d'))

        today = hourless(DateTime())
        yesterday = hourless(DateTime()-1)
        tomorrow = hourless(DateTime()+1)
        future = hourless(DateTime()+7)

        title_no_due_date = 'NO DUE DATE'
        title_today = 'TODAY'
        title_yesterday = 'YESTERDAY'
        title_tomorrow = 'TOMORROW'
        title_future = 'FUTURE'

        request = self.app.REQUEST

        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', description)
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())

        request.set('title', title_no_due_date)
        request.set('due_date', '')
        html = tracker.SubmitIssue(request)

        request.set('title', title_today)
        request.set('due_date', today)
        html = tracker.SubmitIssue(request)

        request.set('title', title_yesterday)
        request.set('due_date', yesterday)
        html = tracker.SubmitIssue(request)

        request.set('title', title_tomorrow)
        request.set('due_date', tomorrow)
        html = tracker.SubmitIssue(request)

        request.set('title', title_future)
        request.set('due_date', future)
        html = tracker.SubmitIssue(request)

        request.set('sortorder', 'due_date')
        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 5)

        # If you sort by due date, the most pressing one should come first.
        # The most pressing one is the one that was due longest ago.
        # Last should be any issues that don't have a due date.

        self.assertEqual([x.getDueDate() for x in seq],
                         [yesterday, today, tomorrow, future, None])

        request.set('reverse', 'true')

        seq = tracker.ListIssuesFiltered()
        self.assertEqual(len(seq), 5)

        self.assertEqual([x.getDueDate() for x in seq],
                         [future, tomorrow, today, yesterday, None])



    def test_change_password(self):
        """test to change your password when you're an acl user in a
        Issue User Folder"""
        tracker = self.folder.tracker
        # create an Issue User Folder inside
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)

        uf = tracker.acl_users

        uf.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [],
                            email="user@test.com",
                            fullname="User Name")

        # first of all, you can't change your password if you're
        # not logged in
        self.assertRaises(UserSubmitError,
                          tracker.IssueUserChangePassword,
                          "secret",
                          "newpassword",
                          "newpassword")

        user = uf.getUserById('user')
        user = user.__of__(uf)
        newSecurityManager(None, user)
        assert getSecurityManager().getUser().getUserName() == 'user'

        # I should now be able to change my password
        self.assertRaises(DataSubmitError,
                          tracker.IssueUserChangePassword,
                          "not right",
                          "newpassword",
                          "newpassword")

        self.assertRaises(DataSubmitError,
                          tracker.IssueUserChangePassword,
                          "secret",
                          "new is",
                          "different")

        tracker.IssueUserChangePassword("secret", "newpass", "newpass")


    def test_catalog_search_by_issuedate(self):
        """it should be possible to search the issuetracker catalog by the issuedate
        """
        # create an issue
        request = self.app.REQUEST

        tracker = self.folder.tracker
        catalog = tracker.getCatalog()
        self.assertTrue('issuedate' in catalog._catalog.indexes.keys())

        request.set('fromname', u'B\xc3\xa9b')
        request.set('email', u'email@address.com')
        request.set('description', u"\xef Description")
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getDefaultUrgency())
        request.set('title', u"Sample issue")
        html = tracker.SubmitIssue(request)

        # find it again
        # just check basic catalog search first
        brains = catalog()
        self.assertTrue(brains)
        self.assertEqual(brains[0].getObject().getTitle(), u"Sample issue")


        brains = catalog(issuedate={'query':DateTime()-1, 'range':'min'})
        self.assertTrue(brains)
        self.assertEqual(brains[0].getObject().getTitle(), u"Sample issue")

    def test_notification_new_issue_urgency(self):
        #if not getattr(self.folder, 'MailHost', None):
        #    dispatcher = self.folder.manage_addProduct['MailHost']
        #    dispatcher.manage_addMailHost('MailHost')

        tracker = self.folder.tracker
        tracker.always_notify = ['john@doe.com']
        tracker.sitemaster_email = 'webmaster@fryit.com'

        B = u'email@address.com'
        Bf = u'From name'

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]
        self.assertEqual(len(issue.getCreatedNotifications()), 1)
        notification = issue.getCreatedNotifications()[0]
        self.assertTrue(notification.isDispatched())
        self.assertEqual(notification.getEmails(), ['john@doe.com'])

        sent_email = base.snatched_emails[-1]
        self.assertTrue("urgency: %s" % tracker.getUrgencyOptions()[-1] \
          in sent_email['subject'])

    def test_notification_with_assigment(self):
        base.snatched_emails = []
        tracker = self.folder.tracker
        tracker.always_notify = ['john@doe.com']
        tracker.sitemaster_email = 'webmaster@fryit.com'

        B = u'email@address.com'
        Bf = u'From name'

        tracker.use_issue_assignment = True
        # add a user to assign stuff to
        tracker._addRole(IssueTrackerUserRole)
        tracker._addRole(IssueTrackerManagerRole)
        from IssueTrackerProduct.IssueUserFolder import manage_addIssueUserFolder
        manage_addIssueUserFolder(tracker, keep_usernames=True)
        tracker.acl_users.userFolderAddUser("user", "secret", [IssueTrackerUserRole], [],
                                            email="user@test.com",
                                            fullname="User Name")
        user = tracker.getAllIssueUsers()[0]

        tracker.include_description_in_notifications = True
        tracker.show_id_with_title = True

        request = self.app.REQUEST
        request.set('title', u'TITLE')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        request.set('assignee', user['identifier'])
        request.form['notify-assignee'] = '1'

        tracker.SubmitIssue(request)

        issue = tracker.getIssueObjects()[0]
        self.assertEqual(len(issue.getCreatedNotifications()), 2)
        for notification in issue.getCreatedNotifications():
            self.assertTrue(notification.isDispatched())
            self.assertTrue(notification.getSuccessEmails())
            self.assertTrue(notification.getEmails() == ['user@test.com'] \
              or notification.getEmails() == ['john@doe.com'])

        self.assertEqual(len(base.snatched_emails), 2)

        last_two = base.snatched_emails[-2:]
        if last_two[0]['to'] == 'user@test.com':
            assignment_email = last_two[0]
            always_email = last_two[1]
        else:
            assignment_email = last_two[1]
            always_email = last_two[0]

        self.assertTrue('Assigned to: User Name' in always_email['msg'])
        self.assertTrue('Urgency: %s' % tracker.getUrgencyOptions()[-1] \
          in always_email['msg'])
        self.assertTrue('DESCRIPTION' in always_email['msg'])

        self.assertTrue('Assigned to: User Name' not in assignment_email['msg'])
        self.assertTrue('urgency: %s' % tracker.getUrgencyOptions()[-1]\
          in assignment_email['subject'])
        self.assertTrue('DESCRIPTION' in assignment_email['msg'])

    def test_avoiding_duplicates(self):
        tracker = self.folder.tracker
        B = u'email@address.com'
        Bf = u'From name'
        request = self.app.REQUEST
        request.set('title', u'TITLE (1)')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)

        request.set('title', u'TITLE (1)')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)

        request.set('title', u'TITLE (2)')
        tracker.SubmitIssue(request)
        self.assertEqual(len(tracker.getIssueObjects()), 2)

    def test_avoiding_duplicates_harder(self):
        tracker = self.folder.tracker
        B = u'email@address.com'
        Bf = u'From name'
        request = self.app.REQUEST
        request.set('title', u'TITLE (1) "peter"')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)

        request.set('title', u'TITLE (1) "peter"')
        request.set('fromname', Bf)
        request.set('email', B)
        request.set('description', u'DESCRIPTION')
        request.set('type', tracker.getDefaultType())
        request.set('urgency', tracker.getUrgencyOptions()[-1])
        tracker.SubmitIssue(request)

        self.assertEqual(len(tracker.getIssueObjects()), 1)

        request.set('title', u'TITLE (1) "chris"')
        tracker.SubmitIssue(request)
        self.assertEqual(len(tracker.getIssueObjects()), 2)

        issues = tracker._searchCatalog('1')
        self.assertEqual(len(issues), 2)

        issues = tracker._searchCatalog('(1)')
        self.assertEqual(len(issues), 2)

        issues = tracker._searchCatalog('peter')
        self.assertEqual(len(issues), 1)

        issues = tracker._searchCatalog('"chris')
        self.assertEqual(len(issues), 1)

        issues = tracker._searchCatalog('"chris"')
        self.assertEqual(len(issues), 1)



################################################################################


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(IssueTrackerTestCase))
    if traversing:
        suite.addTest(makeSuite(TestFunctionalBase))
    return suite


if __name__ == '__main__':
    framework()
