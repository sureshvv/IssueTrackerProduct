# IssueTrackerProduct
#
# Peter Bengtsson <mail@peterbe.com>
# License: ZPL
#

# python
import warnings
import re, sys, cgi, os
from time import time
from string import zfill
try:
    import transaction
except ImportError:
    # we must be in an older than 2.8 version of Zope
    transaction = None

try:
    import simplejson
except ImportError:
    import warnings
    warnings.warn("simplejson no installed (easy_install simplejson)")
    simplejson = None


# Zope
from Acquisition import aq_inner, aq_parent
from AccessControl import ClassSecurityInfo, getSecurityManager
from zLOG import LOG, ERROR, INFO, PROBLEM, WARNING
from DateTime import DateTime

try:
    # >= Zope 2.12
    from webdav.interfaces import IWriteLock
    from App.class_init import InitializeClass
except ImportError:
    # < Zope 2.12
    from webdav.WriteLockInterface import WriteLockInterface as IWriteLock
    from Globals import InitializeClass

try:
    from persistent.mapping import PersistentMapping
    from persistent.list import PersistentList
except ImportError:
    # for old versions of Zope
    PersistentMapping = dict
    PersistentList = list


# Is CMF installed?
try:
    from Products.CMFCore.utils import getToolByName as CMF_getToolByName
except ImportError:
    CMF_getToolByName = None

# Product
from IssueTracker import IssueTracker, debug, safe_hasattr
from TemplateAdder import addTemplates2Class
import Utils
from Utils import unicodify, asciify, merge_changes
from Constants import *
from Errors import *
from Permissions import VMS, ChangeIssuePermission
from I18N import _
from CustomField import CustomFieldsIssueBase, compare_custom_value

#----------------------------------------------------------------------------


# Misc stuff

ss = lambda s: s.strip().lower() # to save some typing space


#----------------------------------------------------------------------------

class IssueTrackerIssue(IssueTracker, CustomFieldsIssueBase):
    """ Issues class as containers """

    meta_type = ISSUE_METATYPE

    _properties=({'id':'title',         'type': 'ustring', 'mode':'w'},
                 {'id':'issuedate',     'type': 'date',   'mode':'w'},
                 {'id':'modifydate',    'type': 'date',   'mode':'w'},
                 {'id':'status',        'type': 'ustring', 'mode':'w'},
                 {'id':'type',          'type': 'ustring', 'mode':'w'},
                 {'id':'urgency',       'type': 'ustring', 'mode':'w'},
                 {'id':'sections',      'type': 'ulines',  'mode':'w'},
                 {'id':'fromname',      'type': 'ustring', 'mode':'w'},
                 {'id':'email',         'type': 'string', 'mode':'w'},
                 {'id':'acl_adder',     'type': 'string', 'mode':'w'},
                 {'id':'url2issue',     'type': 'string', 'mode':'w'},
                 {'id':'confidential',  'type': 'boolean','mode':'w'},
                 {'id':'hide_me',       'type': 'boolean','mode':'w'},
                 {'id':'description',   'type': 'utext',   'mode':'w'},
                 {'id':'display_format','type': 'string', 'mode':'w'},
                 {'id':'subscribers',   'type': 'lines',  'mode':'w'},
                 {'id':'submission_type','type':'string', 'mode':'w'},

                 )


    security = ClassSecurityInfo()

    manage_options = (
        {'label':'Contents', 'action':'manage_main'},
        {'label':'View', 'action':'index_html'},
        {'label':'Properties', 'action':'manage_propertiesForm'}
        )

    # backward compatability
    acl_adder = ''
    submission_type = ''
    detail_changes = []

    def __init__(self, id, title, status, issuetype, urgency, sections,
                 fromname, email, url2issue, confidential, hide_me,
                 description, display_format, issuedate='',
                 acl_adder='', submission_type='',
                 subscribers=None, # keep this parameter (not used) for legacy (remove in a year)
                 due_date=None,
                 ):
        """ init an Issue object """
        self.id = str(id)
        self.title = unicodify(title.strip())
        if isinstance(issuedate, basestring):
            issuedate = DateTime(issuedate)
        self.issuedate = issuedate
        self.modifydate = DateTime()
        self.status = status
        self.type = issuetype
        self.urgency = urgency
        self.sections = sections
        self.fromname = unicodify(fromname)
        if isinstance(email, basestring):
            email = asciify(email, 'ignore')
        self.email = email
        self.url2issue = url2issue
        self.confidential = confidential
        self.hide_me = hide_me
        self.due_date = due_date
        self.description = unicodify(description)
        if display_format:
            self.display_format = display_format
        else:
            self.display_format = self.getDefaultDisplayFormat()
        self.subscribers = []
        self.submission_type = submission_type
        self.actual_time_hours = None
        self.estimated_time_hours = None
        self.email_message_id = None

        if acl_adder is None:
            acl_adder = ''
        self.acl_adder = acl_adder

        self.custom_fields_data = PersistentMapping()

        self.detail_changes = PersistentList()


    def getId(self):
        """ return id """
        return self.id

    def getIssueId(self):
        """ return id
        The reason for having this method is so that one can be sure to called the correct
        getId() since 'getId' is a common function name here in Zope. """
        return self.getId()

    def getGlobalIssueId(self):
        """ return a string that contains both the issuetrackers id and the issue id """
        tmpl = '%s#%s'
        root_id = self.getRoot().getId()
        issue_id = self.getIssueId()
        return tmpl % (root_id, issue_id)

    def relative_url_path(self):
        """ return the url to this issue based on where you are at the moment """
        return self.absolute_url().replace(self.REQUEST.URL1+'/','')

    def getTitle(self):
        """ return title """
        return self.title

    def showTitle(self):
        """ return title html quoted """
        t = self.getTitle()
        if isinstance(t, str):
            return self.HighlightQ(
                    Utils.html_entity_fixer(
                     Utils.tag_quote(t)
                    )
               )
        else:
            return self.HighlightQ(Utils.tag_quote(t))

    def getStatus(self):
        """ return the status of the issue """
        return self.status

    def getURL2Issue(self):
        """ return url2issue """
        return self.url2issue

    def getModifyDate(self):
        """ return modifydate """
        return self.modifydate

    # This method has been made public because it's called so often by the AJAX
    # that there's is no point letting the heavy Zope security machine work
    # on this one.
    security.declarePublic('getModifyTimestamp')
    def getModifyTimestamp(self):
        """ return the modify date as a integer timestamp """
        return "%d\n" % int(self.getModifyDate())

    def _updateModifyDate(self):
        """ set the modify date again """
        self.modifydate = DateTime()

    def getIssueDate(self):
        """ return issuedate """
        return self.issuedate

    def getDueDate(self):
        return getattr(self, 'due_date', None)

    def getFromname(self, issueusercheck=True):
        """ return fromname """
        acl_adder = self.getACLAdder()
        if issueusercheck and acl_adder:
            ufpath, name = acl_adder.split(',')
            try:
                uf = self.unrestrictedTraverse(ufpath)
            except KeyError:
                try:
                    uf = self.unrestrictedTraverse(ufpath.split('/')[-1])
                except KeyError:
                    # the userfolder (as it was saved) no longer exists
                    return self.fromname

            if uf.meta_type == ISSUEUSERFOLDER_METATYPE:
                if uf.data.has_key(name):
                    issueuserobj = uf.data[name]
                    return issueuserobj.getFullname() or self.fromname
            elif CMF_getToolByName and hasattr(uf, 'portal_membership'):
                mtool = CMF_getToolByName(self, 'portal_membership')
                member = mtool.getMemberById(name)
                if member and member.getProperty('fullname'):
                    return member.getProperty('fullname')

        return self.fromname

    def getEmail(self, issueusercheck=True):
        """ return email """
        acl_adder = self.getACLAdder()
        if issueusercheck and acl_adder:
            ufpath, name = acl_adder.split(',')
            try:
                uf = self.unrestrictedTraverse(ufpath)
            except KeyError:
                try:
                    uf = self.unrestrictedTraverse(ufpath.split('/')[-1])
                except KeyError:
                    # the userfolder (as it was saved) no longer exists
                    return self.email

            if uf.meta_type == ISSUEUSERFOLDER_METATYPE:
                if uf.data.has_key(name):
                    issueuserobj = uf.data[name]
                    return issueuserobj.getEmail() or self.email
            elif CMF_getToolByName and hasattr(uf, 'portal_membership'):
                mtool = CMF_getToolByName(self, 'portal_membership')
                member = mtool.getMemberById(name)
                if member and member.getProperty('email'):
                    return member.getProperty('email')

        return self.email

    def getACLAdder(self):
        """ return acl_adder """
        return self.acl_adder

    def _setACLAdder(self, acl_adder):
        """ set acl_adder """
        self.acl_adder = acl_adder

    def getDetailChanges(self):
        return self.detail_changes

    def _addDetailChange(self, change):
        try:
            if isinstance(self.detail_changes, list):
                changes = self.detail_changes

                changes.append(change)
                self.detail_changes = changes
            else:
                _merged_change = False
                try:
                    last_change = self.detail_changes[-1]
                    one_minute = 1.0 / 24 / 60
                    if (change['change_date'] - last_change['change_date']) <= one_minute:
                        if last_change.get('acl_adder') == change.get('acl_adder'):
                            # same user very close together
                            self.detail_changes[-1] = merge_changes(last_change, change)

                            # if someone changed say urgency low->high then immediately after
                            # back to urgency high->low there are no actual changes here.
                            # Then we can pop the last item
                            _actual_changes = [k for (k,v) in self.detail_changes[-1].items()
                                               if isinstance(v, dict) and 'new' in v and 'old' in v]
                            if not _actual_changes:
                                self.detail_changes.pop()
                            _merged_change = True

                except IndexError:
                    # there was no last change
                    pass

                if not _merged_change:
                    self.detail_changes.append(change)


        except AttributeError:
            changes = PersistentList()
            changes.append(change)
            self.detail_changes = changes



    def isRecentlyAdded(self):
        """ return true if the issue was recently added.
        This will be true just after you press save on the Add Issue page.
        """
        if self.REQUEST.get('HTTP_REFERER','').split('/')[-1] in ('AddIssue','QuickAddIssue'):
            # but perhaps you've been on the page for a while now and decide to reload it
            if (DateTime()-self.getIssueDate()) * 24 * 60 < 1:
                # not older than one minute
                return True
        elif self.REQUEST.get('NewIssue'): # the old way
            return True

        return False

    def isYourIssue(self):
        """ return true if the currently logged in user is the same
        user who added this issue. """
        issueuser = self.getIssueUser()
        if issueuser:
            identifier = issueuser.getIssueUserIdentifier()
            identifier = ','.join(identifier)
            if identifier == self.getACLAdder():
                return True
            else:
                # if you're logged in as an issue user then how could
                # the issue have been yours if your identifier
                # is not the same.
                # If this `return False` wasn't here a logged in user
                # would be able to change his email address and then see
                # other peoples issues.
                # However, as you'll see in the comment a few lines below
                # it's also not possible to return True here if the issue
                # was added by an authenticated user.
                return False

        zopeuser = self.getZopeUser()
        if zopeuser:
            path = '/'.join(zopeuser.getPhysicalPath())
            name = zopeuser.getUserName()
            acl_user = path+','+name
            if acl_user == self.getACLAdder():
                return True
            else:
                return False

        # the last remaining chance is if the issue was added by someone
        # who's not logged in but has the same email address.
        if not self.getACLAdder():

            if self.getEmail() == self.getSavedUser('email'):
                return True

        return False

    def getDisplayFormat(self):
        """ return display_format """
        return self.display_format

    def getDescription(self):
        """ return description """
        return self.description

    def getDescriptionPure(self):
        """ return description purified.
        If the description contains HTML for example, remove it."""
        description = self.getDescription()
        if self.getDisplayFormat() =='html':
            # textify() coverts "<tag>Something</tag>" to "Something". Simple.
            description = Utils.textify(description)

            # a very common thing is that the description contains
            # these faux double linebreaks and when you run textify()
            # on '<p>&nbsp;</p>' the result is '&nbsp;'. Too many of
            # those result in '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' which
            # isn't pure and purifying is what this method aims to do
            description = description.replace('<p>&nbsp;</p>','')

        return description

    def getEmailMessageId(self):
        """ if the email was submitted via email it will most likely have
        a message id """
        return getattr(self, 'email_message_id', None)

    def _setEmailMessageId(self, message_id):
        """ set the email message id """
        assert message_id.strip(), "Message_id not valid"
        self.email_message_id = message_id.strip()

    def _setEmailOriginal(self, original_email):
        """ set the original_email attribute """
        self.original_email = original_email

    def hasEmailOriginal(self):
        """ return if we have a 'original_email' attribute set """
        return hasattr(self, 'original_email')

    def ShowOriginalEmail(self, REQUEST):
        """ return the original email text """
        if REQUEST:
            REQUEST.RESPONSE.setHeader('Content-Type','text/plain')
        return self.original_email

    def _findIssueLinks(self, formatted):
        """ return a dictionary where we find each issue link and it's
        relative URL.

        This method is quite slow since it does a check if the issues exist so
        only fire this of rarely.
        """

        root = self.getRoot()
        root_id = root.getId()
        trackerids = [root_id]
        roots_parent = aq_parent(aq_inner(root))
        adjacent_items = roots_parent.objectItems(ISSUETRACKER_METATYPE)
        for adj_issuetracker_id in [one for (one, two) in adjacent_items]:
            trackerids.append(adj_issuetracker_id)
        prefix = self.issueprefix
        zfill_ = self.randomid_length
        # if you set it up to use a length of 3 (the default) and the
        # day you have more than 999 issues you won't match things with
        # issue IDs like 7818. You safely increment this number by 1
        zfill_ += 1

        regex = Utils.getFindIssueLinksRegex(zfill_, trackerids, prefix)

        _inner_template_ = '<a href="%s" title="%s">%s#%s</a>'
        _outer_template_ = '<a href="%s" title="%s">%s#%s</a>'

        def process_find(match):
            find = match.group(1)
            if formatted[match.span()[1]:match.span()[1]+4] != '</a>':

                # deconstruct this find to see if we can to pursue it
                trackerid, issueid = match.group(1).split('#')
                if prefix:
                    if len(issueid.split(prefix))==2:
                        issueid = issueid.split(prefix)[1]

                if issueid.isdigit() and not issueid.startswith('0'):
                    # this can happen if someone sloppily enters #123
                    # instead of #0123 when '0123' is the real issue id

                    issueid = zfill(issueid, zfill_)
                if not trackerid or trackerid == root_id:
                    try:
                        issue = root.getIssueObject(issueid)
                        issue_url = issue.absolute_url_path()
                        issue_title = issue.getTitle()
                        #title_tag = "%s (%s)" % (issue_title, issue.getStatus().capitalize())
                        if self.ShowIdWithTitle():
                            title_tag = "#%s %s" % (issue.getId(), issue_title)
                        else:
                            title_tag = "%s" % issue_title
                        return _inner_template_ % (issue_url, title_tag, trackerid, issueid)
                    except AttributeError:
                        # the issue doesn't exist in this issuetracker anymore
                        # and there's nothing we can do about that
                        pass

                elif hasattr(roots_parent, trackerid):
                    adjacent_tracker = getattr(roots_parent, trackerid)
                    try:
                        # make it a link!!
                        issue = adjacent_tracker.getIssueObject(issueid)
                        issue_url = issue.absolute_url_path()
                        issue_title = issue.getTitle()
                        return _outer_template_ % (issue_url, issue_title, trackerid, issueid)
                    except AttributeError:
                        # the issue doesn't exist there anymore :(
                        # nothing we can do about that
                        pass

            return find


        return regex.sub(process_find, formatted)


    def _unicode_title(self):
        """ make the title of this issue a unicode string """
        self.title = unicodify(self.title)

    def _unicode_description(self):
        """ make the description of this issue a unicode string """
        self.description = unicodify(self.description)
        self._prerendered_description = unicodify(self._prerendered_description)

    def _prerender_description(self):
        """ Run the methods that pre-renders the description on the issue. """
        description = self.getDescription()
        display_format = self.getDisplayFormat()

        formatted = self.ShowDescription(description+' ', display_format)

        if self.getSubmissionType()=='email':
            use_newline_to_br = True
            if display_format == 'plaintext':
                use_newline_to_br = False

            attrs = 'class="sig"'
            formatted = Utils.highlight_signature(formatted, attrs,
                                                  use_newline_to_br=True)

        formatted = self._findIssueLinks(formatted)

        self._prerendered_description = formatted


    def _getFormattedDescription(self, force_refresh=False):
        """ return the formatted description (prerendered) or not """
        if force_refresh:
            self._prerender_description()

        if getattr(self, '_prerendered_description', None):
            formatted = self._prerendered_description
        else:
            description = self.getDescription()
            display_format = self.getDisplayFormat()
            formatted = self.ShowDescription(description+' ', display_format)

            if self.getSubmissionType()=='email':
                attrs = 'class="sig"'
                formatted = Utils.highlight_signature(formatted, attrs)
        return formatted


    def showDescription(self, signature_hidden=False):
        """ combine ShowDescription (which is generic) with this
        issues display format."""
        formatted = self._getFormattedDescription()
        highlighted = self.HighlightQ(formatted)

        return highlighted

    def getSubmissionType(self):
        """ return how it was submitted, empty string if not found """
        return getattr(self, 'submission_type', '')

    def getSections(self):
        """ return the sections """
        return self.sections

    def getUrgency(self):
        """ return urgency """
        return self.urgency

    def getType(self):
        """ return type """
        return self.type

    def countFileattachments(self):
        """ return how many file attachments this issue has """
        return len(self.objectValues('File'))


    security.declareProtected(VMS, 'manage_editProperties')
    def manage_editProperties(self, REQUEST):
        """ re-prerender the description of the issue after manual change """
        result = IssueTracker.manage_editProperties(self, REQUEST)
        try:
            self._prerender_description()
        except:
            if DEBUG:
                raise
            else:
                try:
                    err_log = self.error_log
                    err_log.raising(sys.exc_info())
                except:
                    pass
                LOG(self.__class__.__name__, ERROR,
                    "Unable to _prerender_description() in manage_editProperties()",
                    error=sys.exc_info())
        return result

    def manage_afterAdd(self, REQUEST, RESPONSE):
        """ intercept so that we prerender always """
        return
        try:
            self._prerender_description()
        except:
            if DEBUG:
                raise
            else:
                try:
                    err_log = self.error_log
                    err_log.raising(sys.exc_info())
                except:
                    pass
                LOG(self.__class__.__name__, ERROR,
                    "Unable to _prerender_description() after add",
                    error=sys.exc_info())


    security.declareProtected(VMS, 'assertAllProperties')
    def assertAllProperties(self):
        """ make sure issue has all properties """
        props = {'title':'', 'issuedate':DateTime(),
                 'status':self.getStatuses()[0], 'type':self.default_type,
                 'urgency':self.default_urgency,
                 'sections':self.defaultsections,
                 'fromname':'', 'email':'', 'url2issue':'',
                 'confidential':False, 'hide_me':False,
                 'description':'',
                 'display_format':self.getDefaultDisplayFormat(),
                 'subscribers':[],
                 'modifydate':self.bobobase_modification_time(),
                 'actual_time_hours': None,
                 'estimated_time_hours': None,
                 }

        count = 0
        for key, default in props.items():
            if not self.__dict__.has_key(key):
                self.__dict__[key] = default
                count += 1
            elif key=='sections' and isinstance(self.sections, tuple):
                self.sections = list(self.sections)
                count += 1

        # check that self.fromname is as good as self.getFromname()
        attr_fromname = self.getFromname(issueusercheck=False)
        linked_fromname = self.getFromname(issueusercheck=True)
        if linked_fromname != attr_fromname:
            # for sanity, check that the linked fromname is ok
            if linked_fromname:
                self.fromname = linked_fromname
                count += 1

        # check that self.email is as good as self.getFromname()
        attr_email = self.getEmail(issueusercheck=False)
        linked_email = self.getEmail(issueusercheck=True)
        if linked_email != attr_email:
            # for sanity, check that the linked email is ok
            if linked_email:
                self.email = linked_email
                count += 1

        return count

    security.declareProtected('View', 'index_html')
    def index_html(self, REQUEST,
                   savedraftfollowup=False,
                   cancelfollowup=False,
                   previewfollowup=False,
                   savefollowup=False,
                   *args, **kw):
        """ show the issue

        The parameters savedraftfollowup, cancelfollowup, previewfollowup and
        savedraftfollowup are all here because that's the only way to make the
        buttons on the followup form all go to this place yet do different
        things.
        """
        if self.canViewIssue():
            #self.RememberIssueVisit(self.getId())
            self.RememberRecentIssue(self.getId(), 'viewed')

            if REQUEST.get('fileattachment', []):
                fake_fileattachments = self._getFakeFileattachments(REQUEST.get('fileattachment'))
                if fake_fileattachments:
                    m = "Filename entered but no file content"
                    SubmitError = {'fileattachment':m}
                    self.REQUEST.set('previewissue',None)
                    return self.ShowIssue(self, self.REQUEST, FollowupSubmitError=SubmitError, **kw)

            # XXX is this really necessary every time?
            self._uploadTempFiles()

            if savedraftfollowup:
                return self.SaveDraftThread(REQUEST, *args, **kw)
            elif cancelfollowup:
                if self.SaveDrafts():
                    self._cancelDraftThreads()
                # necessary to overwrite the anchor so that it's not #followup
                REQUEST.RESPONSE.redirect(self.absolute_url() + "#top")
                return "redirecting"
            elif savefollowup:
                return self.ModifyIssue(REQUEST, *args, **kw)
            elif previewfollowup:
                self.REQUEST.set('showpreview', True)

            if REQUEST.REQUEST_METHOD == 'POST' and REQUEST.get('edit-actual-time'):
                assert self.UseActualTime() and self.UseFollowupActualTime()
                actual_time_hours = REQUEST.get('actual_time_hours').strip()
                thread = getattr(self, REQUEST.get('edit-actual-time'))
                before = thread.actual_time_hours
                if before is None:
                    before = 0.0

                if not actual_time_hours:
                    thread.actual_time_hours = 0.0
                else:
                    thread.actual_time_hours = self._parseTimeHours(actual_time_hours)
                self.actual_time_hours += thread.actual_time_hours - before
                ids = list(self.objectIds(ISSUETHREAD_METATYPE))
                index = ids.index(thread.getId()) + 1
                return REQUEST.RESPONSE.redirect(self.absolute_url() + '#i%s' % index)

            session_key = '%s-%s-notify_emails' % (self.getRoot().getId(),
                                                   self.getId())

            notify_emails = self.get_session(session_key)
            if notify_emails:
                self.REQUEST.set('notify-more-options', '1')
                self.REQUEST.set('notify_email', notify_emails)

            return self.ShowIssue(self, self.REQUEST, **kw)
        else:
            response = self.REQUEST.RESPONSE
            listpage = '/%s'%self.whichList()
            response.redirect(self.getRootURL()+listpage)

    def _cancelDraftThreads(self, autosaved_only=False):
        """remove any draft threads you have in this issue"""
        followupdrafts = self.getMyFollowupDrafts(issueid=self.getId(),
                                                  autosaved_only=autosaved_only)
        for draft in followupdrafts:
            # this will remove it from the cookie
            self.DeleteDraftThread(draft.getId())
            # this will remove it independent of cookie
            self._dropDraftThread(draft.getId())

        if getattr(self,'_v_recent_draft', None):
            if self._v_recent_draft.issueid == self.getId():
                del self._v_recent_draft

        assert not self.getMyFollowupDrafts(issueid=self.getId())

    security.declarePrivate('canViewIssue')
    def canViewIssue(self):
        """return true if you should be allowed to see the issue """
        return not self.isConfidential() or self.hasManagerRole() or self.isYourIssue()

    def isConfidential(self):
        """ check confidential property """
        return getattr(self, 'confidential', False)
    IsConfidential = isConfidential

    def isHidden(self):
        """ return hide_me """
        return self.hide_me

    def getEstimatedTimeHours(self):
        """ return estimated_time_hours """
        return getattr(self, 'estimated_time_hours', None)

    def getActualTimeHours(self):
        """ return actual_time_hours """
        return getattr(self, 'actual_time_hours', None)


    def _parseTimeHours(self, hours):
        """ return a floating point number from the number of hours
        input. This can be in the form of a float, an int or a
        string containing the words 'hours' """
        try:
            return float(hours)
        except ValueError:
            if isinstance(hours, basestring):
                if not hours.strip():
                    return 0.0

                try:
                    return float(hours.replace('hours','').replace('hour',''))
                except ValueError:
                    # try to parse it
                    minutes_ = 0
                    hours_ = 0

                    # perhaps they've written "15 minutes"
                    minutes_regex = re.compile('((\d{1,2})\sminutes)')
                    if minutes_regex.findall(hours):
                        whole, number = minutes_regex.findall(hours)[0]
                        try:
                            minutes_ = int(number)
                            hours = hours.replace(whole, '')
                        except KeyError:
                            pass

                    hours_regex = re.compile(r'((\d{1,2})\s*(hour|hours))', re.I)
                    if hours_regex.findall(hours):
                        whole, number, __ = hours_regex.findall(hours)[0]

                        try:
                            hours_ = int(number)
                            hours = hours.replace(whole, '')
                        except KeyError:
                            pass

                    return hours_ + minutes_/60.0

        # still here?!
        raise ValueError, "Hours not recognized, enter only a numeral (or decimal)"

    def parse_and_showTimeHours(self, value, **kwargs):
        """wrapper on showTimeHours() that only works if we can first parse the
        value. This is so that we can use the parsing when previewing the
        followup."""
        try:
            return self.showTimeHours(self._parseTimeHours(value), **kwargs)
        except ValueError:
            return ""

    def getPreviewTitle(self, oldstatus, action):
        """ Get what the title of thread will be (via the web only) """
        action = unicodify(ss(action))

        statuses_and_verbs = self.getStatusesMerged(asdict=1)
        lowercase_values = {}
        statuses_and_verbs_reversed = {}
        for key, value in statuses_and_verbs.items():
            lowercase_values[value.lower()] = value
            statuses_and_verbs_reversed[value] = key

        if lowercase_values.has_key(action):
            past_tense = statuses_and_verbs_reversed[lowercase_values[action]]
        else:
            action = 'add followup'

        if action == 'add followup':
            gentitle = 'Added Issue followup'
        else:
            gentitle = 'Changed status from %s to %s'%\
                       (oldstatus.capitalize(), past_tense.capitalize())

        return gentitle


    def ExtensionForm(self, options):
        """ set some REQUEST variables to be used by form_followup. """
        request = self.REQUEST

        # extract what we need from this caller templates options
        SubmitError = options.get('FollowupSubmitError',
                                  options.get('SubmitError'))


        draft_followup_id = options.get('draft_followup_id',
                                        request.get('draft_followup_id'))


        draft_saved = options.get('draft_saved')

        if draft_followup_id:
            if not isinstance(draft_followup_id, basestring):
                raise ValueError, "draft_followup_id not a string (%r)" % draft_followup_id

            # take the action from the draft
            container = self.getDraftsContainer()
            if safe_hasattr(container, draft_followup_id):
                draft_object = getattr(container, draft_followup_id)
                if not request.get('action'):
                    request.set('action', draft_object.action)
                if not request.get('comment'):
                    request.set('comment', draft_object.getComment())
                if not request.get('fromname'):
                    request.set('fromname', draft_object.getFromname())
                if not request.get('email'):
                    request.set('email', draft_object.getEmail())
                if not request.get('display_format'):
                    request.set('display_format', draft_object.display_format)
                if not request.get('actual_time_hours') and getattr(draft_object, 'actual_time_hours', None):
                    request.set('actual_time_hours', draft_object.actual_time_hours)

        request_action = unicodify(request.get('action','')).lower()

        if request_action == 'delete':
            return self.form_delete(SubmitError=SubmitError)

        if request_action == 'rejectassignment':
            otherTitle = "Reject issue assignment"
            request.set('otherActionTitle', otherTitle)
            request.set('otherComment', "Optional comment")
            request.set('otherAction', 'rejectassignment')

        elif request_action != 'add followup':
            title, action, comment = self._constructOtherTitles(self.status, request_action)
            if title:
                request.set('otherActionTitle', title)
            if action:
                request.set('otherAction', action)
            if comment:
                request.set('otherComment', comment)

        return self.form_followup(SubmitError=SubmitError,
                                  draft_followup_id=draft_followup_id,
                                  draft_saved=draft_saved)

    def _constructOtherTitles(self, issuestatus, action):
        """ return a suitable title for the action and verb """
        issuestatus = issuestatus.lower()
        action = ss(action).replace(' ','')
        otherTitle = _(u"Added Issue Followup")
        otherAction = _(u"Add Followup")
        otherComment = u""

        for status, verb in self.getStatusesMerged(aslist=1):
            if ss(verb).replace(' ','') == action:
                otherTitle = _(u'Change status from') + u' '
                otherTitle += u'<i>%s</i> ' % issuestatus.capitalize()
                otherTitle += u'to <i>%s</i>' % status.capitalize()
                otherAction = verb.capitalize()
                otherComment = _(u"Optional comment")
                break

        return otherTitle, otherAction, otherComment


    def ManagerOptionsExtend(self):
        """ Determine which forms to show to Managers """
        request = self.REQUEST

        print " * * * ManagerOptionsExtend  * * * "

        has_key_special = self.has_key_special
        get_special_key = self.get_special_key

        do_preview = 0
        if has_key_special('IssueAction') and has_key_special('previewissue'):
            do_preview = 1

        form = ''
        if has_key_special('IssueAction') and not do_preview:
            action = get_special_key('IssueAction')
            return getattr(self,request['issueID']).ModifyIssue(action=action)
        elif has_key_special('IssueAction_AddFollowup'):
            request.set('no_quick_formfollowup',1)
            return self.form_followup()
        elif has_key_special('IssueAction_Delete'):
            return self.form_delete()
        else:
            issuestatus = self.status.lower()
            for item in self.getStatusesMerged(aslist=1):
                status, verb = item
                action = 'IssueAction_%s'%verb.replace(' ','').capitalize()
                if has_key_special(action):
                    otherTitle = 'Change status from '
                    otherTitle += '<i>%s</i> '%issuestatus.capitalize()
                    otherTitle += 'to <i>%s</i>'%status.capitalize()
                    request.set('otherActionTitle', otherTitle)
                    request.set('otherAction', verb.capitalize())
                    request.set('otherComment', 'Optional comment')
                    request.set('whatAction', action)
                    request.set('no_quick_formfollowup',1)
                    return self.form_followup()

            else:
                return self.manager_options()


    def AnonymousOptionsExtend(self):
        """ Determine which forms to show to Anonymous """
        request = self.REQUEST

        has_key_special = self.has_key_special
        get_special_key = self.get_special_key

        do_preview = 0
        if has_key_special('IssueAction') and has_key_special('previewissue'):
            do_preview = 1

        form = ''
        if has_key_special('IssueAction') and not do_preview:
            action = get_special_key('IssueAction')
            return getattr(self,request['issueID']).ModifyIssue(action=action)
        elif has_key_special('IssueAction_AddFollowup'):
            form = self.form_followup()
            request.set('no_quick_formfollowup',1)
        else:
            form = self.anonymous_options()

        return form


    def ModifyIssue(self, REQUEST, action=None):
        """ advanced change to issue properties """
        request = self.REQUEST
        SubmitError = {}

        if action is None:
            action = request.get('action', 'Add followup')

        issueobject = self
        action = unicodify(ss(action))
        oldstatus = self.status
        prefix = self.issueprefix

        comment = request.get('comment','').strip()
        if comment.endswith('<br />'):
            comment = comment[:-6].strip()

            while comment.endswith('<p>&nbsp;</p>'):
                comment = comment[:-len('<p>&nbsp;</p>')].strip()
            while comment.startswith('<p>&nbsp;</p>'):
                comment = comment[len('<p>&nbsp;</p>'):].strip()

        if not request.has_key('display_format'):
            saved_display_format = self.getSavedTextFormat()
            if saved_display_format:
                request.set('display_format', saved_display_format)
            else:
                request.set('display_format', self.getDefaultDisplayFormat())

        actual_time_hours = request.get('actual_time_hours')
        if actual_time_hours and self.UseActualTime() and self.UseFollowupActualTime():
            hours = self._parseTimeHours(actual_time_hours.strip())
            assert isinstance(hours, float)
        else:
            hours = None

        req_manager = True # require manager by default
        addfollowup = False
        past_tense = None
        statuses_and_verbs = self.getStatusesMerged(asdict=True)
        lowercase_values = {}
        statuses_and_verbs_reversed = {}
        for key, value in statuses_and_verbs.items():
            lowercase_values[value.lower()] = value
            statuses_and_verbs_reversed[value] = key

        if lowercase_values.has_key(action):
            past_tense = statuses_and_verbs_reversed[lowercase_values[action]]
            addfollowup = True

        elif action == 'delete':
            DeleteIssue(self, self.id)
            addfollowup = False
            redirect_url = request.URL2
        elif action == 'add followup':
            addfollowup = True
            req_manager = False

        if req_manager and not self.hasManagerRole():
            # the chosen action requires manager role,
            # but the person is not a manager
            self.redirectlogin(came_from=self.absolute_url())

        if past_tense is not None and self.status != past_tense:
            self.status = past_tense
        else:
            if self.status == past_tense:
                action = 'add followup'
                REQUEST.set('action', action)
                if not comment:
                    # oops! someone is accidently trying to set the status of this issue
                    # even though it's already set and what's worse, they haven't entered
                    # a comment. Then redirect them out like this...
                    url = issueobject.absolute_url()
                    count = self.countThreads()
                    if count:
                        url += '#i%s' % count
                    return self.REQUEST.RESPONSE.redirect(url)

            # anything else means that the comment_description
            # cannot be empty
            if not Utils.SimpleTextPurifier(comment):
                err = "When submitting a followup you can not leave "\
                      "the description empty"
                SubmitError['comment'] = err
            elif self.containsSpamKeywords(comment, verbose=True):
                SubmitError['comment'] = _("Contains spam keywords")

            # first make sure the email address is ascii
            request['email'] = asciify(request.get('email',''))
            _invalid_name_chars = re.compile('|'.join([re.escape(x) for x in list('<>;\\')]))
            if _invalid_name_chars.findall(request.get('fromname','')):
                SubmitError['fromname'] = u'Contains not allowed characters'
            if _invalid_name_chars.findall(request.get('email','')):
                SubmitError['email'] = u'Contains not allowed characters'

            # check for spambots
            if self.useSpambotPrevention():
                captcha_numbers = request.get('captcha_numbers','').strip()
                captchas_used = request.get('captchas')
                if isinstance(captchas_used, basestring):
                    captchas_used = [captchas_used]

                if not captcha_numbers:
                    m = _("Enter the numbers shown to that you are not a spambot")
                    SubmitError['captcha_numbers'] = m
                else:
                    errors = None
                    for i, nr in enumerate(captcha_numbers):
                        try:
                            if int(nr) != int(self.captcha_numbers_map.get(captchas_used[i])):
                                errors = True
                                break
                        except ValueError:
                            errors = True
                            break

                    if errors:
                        # use this oppurtunity to clean up what they tried to enter
                        captcha_numbers = request.get('captcha_numbers','').strip()
                        captcha_numbers = re.sub('[^\d]','', captcha_numbers).strip()
                        request.set('captcha_numbers', captcha_numbers)

                        m = _("Incorrect numbers matching")
                        SubmitError['captcha_numbers'] = m
                    else:
                        self._rememberProvenNotSpambot()

            if REQUEST.get('fileattachment', []):
                fake_fileattachments = self._getFakeFileattachments(request.get('fileattachment'))
                if fake_fileattachments:
                    m = "Filename entered but no file content"
                    SubmitError['fileattachment'] = m

            if SubmitError:
                return self.ShowIssue(self, REQUEST, FollowupSubmitError=SubmitError)

        # most actions may perhaps add a little comment
        if addfollowup:

            randomid_length = self.randomid_length
            if randomid_length > 3:
                randomid_length = 3

            genid = issueobject.generateID(randomid_length,
                                           prefix=prefix+'thread',
                                           meta_type=ISSUETHREAD_METATYPE,
                                           use_stored_counter=False)

            if action == 'add followup':
                gentitle = "Added Issue followup"
            else:
                gentitle = 'Changed status from %s to %s'%\
                           (oldstatus.capitalize(), past_tense.capitalize())

            # fix variables
            acl_adder = None
            issueuser = self.getIssueUser()
            cmfuser = self.getCMFUser()
            zopeuser = self.getZopeUser()
            if issueuser:
                acl_adder = ','.join(issueuser.getIssueUserIdentifier())
            elif zopeuser:
                path = '/'.join(zopeuser.getPhysicalPath())
                name = zopeuser.getUserName()
                acl_adder = ','.join([path, name])

            fromname = request.get('fromname','').strip()
            ckey = self.getCookiekey('name')
            if issueuser and issueuser.getFullname():
                fromname = issueuser.getFullname()
            elif cmfuser and cmfuser.getProperty('fullname'):
                fromname = cmfuser.getProperty('fullname')
            elif not request.get('fromname') and self.has_cookie(ckey):
                fromname = self.get_cookie(ckey)
            elif request.get('fromname'):
                self.set_cookie(ckey, fromname)

            email = request.get('email','').strip()
            ckey = self.getCookiekey('email')
            if issueuser and issueuser.getEmail():
                email = issueuser.getEmail()
            elif cmfuser and cmfuser.getProperty('email'):
                email = cmfuser.getProperty('email')
            elif not request.get('email') and self.has_cookie(ckey):
                email = self.get_cookie(ckey)
            elif request.get('email'):
                self.set_cookie(ckey, asciify(email, 'replace'))

            if request.get('display_format'):
                display_format = request.get('display_format')
                if issueuser:
                    issueuser.setDisplayFormat(display_format)
            else:
                display_format = self.getDefaultDisplayFormat()
                if issueuser:
                    if issueuser.getDisplayFormat():
                        display_format = issueuser.getDisplayFormat()


            # update Thread object
            title  = gentitle
            threaddate = DateTime()

            #
            # Before we save the thread object, just make a duplication
            # check and if somehting found, redirect there.
            #
            duplicate_thread = self._check4Duplicate(title, comment)
            if duplicate_thread:
                url = issueobject.absolute_url()
                url += '#i%s' % self.countThreads()
                return self.REQUEST.RESPONSE.redirect(url)

            # create an Thread object
            create_method = issueobject._createThreadObject
            followupobject = create_method(genid, title, comment,
                                           threaddate, fromname,
                                           email, display_format,
                                           acl_adder,
                                           actual_time_hours=hours)
            if hours:
                issueobject.increment_issue_actual_time(followupobject)

            followupobject.index_object()

            # update the parent issue
            self._updateModifyDate()

            # Also upload the fileattachments
            self._moveTempfiles(followupobject)

            # upload new file attachments
            if request.get('fileattachment', []):
                self._uploadFileattachments(followupobject, request.get('fileattachment'))
                followupobject.index_object(idxs=['filenames'])

            self.nullifyTempfolderREQUEST()

            if request.form.get('draft_followup_id'):
                self._dropDraftThread(request.form.get('draft_followup_id'))

            if self.SaveDrafts():
                # make sure there aren't any drafts that match
                # this recently added followupobject
                self._dropMatchingDraftThreads(followupobject)

                # in fact, drop all drafts in this issue
                self._cancelDraftThreads(autosaved_only=True)

            if not self.doDispatchOnSubmit() and followupobject.getEmail():
                # Notifications aren't sent out immediately, that means that
                # there's a chance of a notification already exists inside
                # this issue that is designated to the submitter of this followup.
                self._removeUnsentNotifications(followupobject.getEmail())

            always_email_addresses = []
            if self.AlwaysNotifyEverything():
                always = self.getAlwaysNotify()
                checked = [self._checkAlwaysNotify(x, format='list')
                           for x in always]
                for valid, (name_, email_) in checked:
                    if not valid:
                        continue
                    if email_ == email:
                        # don't send to the email to skip
                        continue
                    if self.ValidEmailAddress(email_):
                        always_email_addresses.append(email_)

            if request.get('notify-more-options'):
                email_addresses = request.get('notify_email')
                # check that they're all email address that are possible
                possible_email_addresses = self.Others2Notify(do='email',
                                                              emailtoskip=email)
                email_addresses = [x.strip() for x
                                   in email_addresses
                                   if x.strip() and x.strip() in possible_email_addresses]

                if always_email_addresses:
                    email_addresses.extend(always_email_addresses)
                    email_addresses = Utils.uniqify(email_addresses)

                if email_addresses:
                    self.sendFollowupNotifications(followupobject,
                              email_addresses, gentitle,
                              status_change=action == 'add followup')


                    session_key = '%s-%s-notify_emails' % (self.getRoot().getId(),
                                                           self.getId())
                    if email_addresses == possible_email_addresses:
                        # forget this session variable because the user has gone
                        # back to selecting all email addresses possible
                        self.delete_session(session_key)
                    else:
                        # put this in a session variable so the next time you get to
                        # this followup form it will preselect the same notification
                        # options.
                        self.set_session(session_key, email_addresses)

            elif request.has_key('notify'):

                # now, create and email-alert-queue object
                # using filtered email address
                # get who to notify
                email_addresses = self.Others2Notify(do='email',
                                                     emailtoskip=email)
                if always_email_addresses:
                    email_addresses.extend(always_email_addresses)
                    email_addresses = Utils.uniqify(email_addresses)

                if email_addresses:
                    self.sendFollowupNotifications(followupobject,
                              email_addresses, gentitle,
                              status_change=action == 'add followup')

            elif always_email_addresses:
                self.sendFollowupNotifications(followupobject,
                              always_email_addresses, gentitle,
                              status_change=action == 'add followup')


        objectIds = issueobject.objectIds(ISSUETHREAD_METATYPE)
        redirect_url = '%s#i%s'%(issueobject.absolute_url(),
                                 len(objectIds))

        # catalog
        issueobject.unindex_object()
        issueobject.index_object()

        # ready ! redirect!
        request.RESPONSE.redirect(redirect_url)


    def _removeUnsentNotifications(self, to_email):
        """ for all the unsent notification inside this issue, those that
        are designated to @to_email can be discarded.

        When doing this, if by removing this email from the notificaiton's
        list of emails, the list becomes empty then remove the notification
        object.

        The reason for doing this is that it's assumed that this @to_email
        has already participated in the issue and therefore don't need
        to be notified.
        """

        def filter_function(notification, email):
            if not notification.isDispatched():
                if email.lower() in [x.lower() for x in notification.getEmails()]:
                    return True
            return False

        notifications = [x for x in self.getCreatedNotifications()
                           if filter_function(x, to_email.lower())]

        del_notification_ids = []
        for notification in notifications:
            new_emails_list = [x for x in notification.getEmails()
                                 if x.lower() != to_email.lower()]
            if new_emails_list:
                notification._setEmails(new_emails_list)
            else:
                del_notification_ids.append(notification.getId())

        if del_notification_ids:
            self.manage_delObjects(del_notification_ids)


    security.declarePrivate('sendFollowupNotifications')
    def sendFollowupNotifications(self, followupobject, email_addresses, change,
                                  status_change=False):

        prefix = self.issueprefix

        # create id for notification
        mtype = NOTIFICATION_META_TYPE
        notifyid = self.generateID(4, prefix+"notification",
                                   meta_type=mtype,
                                   use_stored_counter=0)

        title = self.title
        issueID = self.id
        anchorname = len(self.objectIds(ISSUETHREAD_METATYPE))
        emails = email_addresses
        date = DateTime()

        assert self.hasIssue(issueID), "This notification has no issue"

        if status_change:
            new_status = self.getStatus()
        else:
            new_status = ''


        notification_comment = followupobject.getCommentPure()
        notification = IssueTrackerNotification(
                            notifyid, title, issueID,
                            emails,
                            followupobject.fromname,
                            comment=notification_comment,
                            anchorname=anchorname,
                            change=change,
                            new_status=new_status,
                            )
        self._setObject(notifyid, notification)
        notifyobject = getattr(self, notifyid)

        # use the dispatcher to try to send
        # this notification right now.
        # there is no big deal if the dispatcher crashes here
        # because the notification is saved and the dispatcher
        # can be invoked some other time manually
        if self.doDispatchOnSubmit():
            try:
                self.dispatcher()
            except:
                try:
                    err_log = self.error_log
                    err_log.raising(sys.exc_info())
                except:
                    pass
                LOG(self.__class__.__name__, PROBLEM,
                   'Email could not be sent', error=sys.exc_info())



    def _check4Duplicate(self, title, comment, fromname=None, email=None,
                         email_message_id=None
                         ):
        """ check if there is an exact replica of this issue """

        # A duplication
        # is only a duplication if the last added thread is exactly the
        # same. Suppose some does this:
            # from Open -> Completed (comment fixed!)
            # from Completed -> Open (comment still doesn't work!)
            # from Open -> Completed (comment fixed!)
            # then the first and last threads are identical but the flow
            # is perfectly valid.
            #
        allthreads = self.ListThreads()
        for thread in allthreads:


            if thread.getTitle() == title and thread.getComment() == comment:
                #
                # looking like it's a duplicate.
                #

                # check for match on email_message_id
                if email_message_id and thread.getEmailMessageId():
                    if ss(email_message_id) == ss(thread.getEmailMessageId()):
                        return thread

                # Before we return this
                # thread object, do a few pessimistic tests
                if fromname and ss(fromname) != ss(thread.getFromname()):
                    continue

                if email and ss(email) != ss(thread.getEmail()):
                    continue

                # If it was posted more than 5 minutes ago
                days_ago = DateTime() - thread.getThreadDate()
                if days_ago * 24 * 60 >= 5:
                    continue

                return thread

        # not a duplicate
        return None


    def _createThreadObject(self, id, title, comment, threaddate,
                            fromname, email, display_format,
                            acl_adder='', submission_type='',
                            email_message_id=None,
                            actual_time_hours=None):
        """ Crudely create thread object. No checking. """
        thread = IssueTrackerIssueThread(id, title, comment, threaddate,
                                         fromname, email, display_format,
                                         acl_adder=acl_adder,
                                         submission_type=submission_type,
                                         actual_time_hours=actual_time_hours)
        self._setObject(id, thread)

        # get that object
        threadobject = getattr(self, id)

        if email_message_id:
            threadobject._setEmailMessageId(email_message_id)

        return threadobject


    def isAllowedToChangeIssues(self):
        """ return true if the logged in user is allowed to change issue details """
        user = getSecurityManager().getUser()
        here = self
        return self.AllowIssueAttributeChange() and user.has_permission(ChangeIssuePermission, here)

    def showChangeKey(self, key):
        if key == 'url2issue':
            return _(u"URL")
        elif key == 'estimated_time_hours':
            return _(u"Estimated time")
        elif key == 'actual_time_hours':
            return _(u"Actual time")
        elif key == 'due_date':
            return _(u"Due date")

        return key.capitalize()

    def showChangedDetail(self, key, value):
        if isinstance(value, (tuple, list)):
            return ', '.join(value)

        if value:
            if key in ('estimated_time_hours', 'actual_time_hours'):
                return self.showTimeHours(value, show_unit=True)
            elif key == 'url2issue':
                href = '<a href="%s">%s</a>' % (self.showURL2Issue(value, href=True),
                                                self.showURL2Issue(value))
                return href
        else:
            if key in ('estimated_time_hours', 'actual_time_hours'):
                return _(u"n/a")

        if value:
            return Utils.html_quote(value)
        return u''


    def getUserDetailsByACLAdder(self, acl_adder):
        """ return (name, email) of the user that is this acl user """
        ufpath, name = acl_adder.split(',')
        try:
            uf = self.unrestrictedTraverse(ufpath)
        except KeyError:
            try:
                uf = self.unrestrictedTraverse(ufpath.split('/')[-1])
            except KeyError:
                # the userfolder (as it was saved) no longer exists
                return {}

        if uf.meta_type == ISSUEUSERFOLDER_METATYPE:
            if uf.data.has_key(name):
                issueuserobj = uf.data[name]
                return dict(fromname=issueuserobj.getFullname() or self.fromname,
                            email=issueuserobj.getEmail() or self.email)

        elif CMF_getToolByName and hasattr(uf, 'portal_membership'):
            mtool = CMF_getToolByName(self, 'portal_membership')
            member = mtool.getMemberById(name)
            if member.getProperty('fullname'):
                return dict(fromname=member.getProperty('fullname'),
                            email=member.getProperty('email'))

        return {}


    security.declareProtected(ChangeIssuePermission, 'editIssueDetails')
    def editIssueDetails(self, sections=None, type=None, urgency=None,
                         confidential=False, url2issue=None,
                         estimated_time_hours=None,
                         actual_time_hours=None,
                         due_date=None,
                         REQUEST=None):
        """ used post submission to change some of the smaller details. """
        assert self.AllowIssueAttributeChange(), "Issue attribute change not enabled"

        change = {}

        if REQUEST is not None:
            SubmitError = {}
            # validate the custom fields
            # Check any of the added custom fields if they have a validation expression
            for field in self.getCustomFieldObjects():
                if field.isMandatory():
                    # if the input type is 'file' bool(request.get(field.getId())) will
                    # be true even if the file was empty
                    if field.getInputType() == 'file':
                        # only considered empty if the file is not a file
                        if REQUEST.get(field.getId()):
                            # we need to make the check
                            if not getattr(REQUEST.get(field.getId()), 'filename', None):
                                SubmitError[field.getId()] = _(u"Empty")
                        else:
                            SubmitError[field.getId()] = _(u"Empty")
                    elif not REQUEST.get(field.getId()):
                        SubmitError[field.getId()] = _(u"Empty")
                    else:
                        valid, message = field.testValidValue(REQUEST.get(field.getId()))
                        if not valid:
                            if not message:
                                message = '*failed the validation test*'
                            SubmitError[field.getId()] = message
                else:
                    valid, message = field.testValidValue(REQUEST.get(field.getId()))
                    if not valid:
                        if not message:
                            message = '*failed the validation test*'
                        SubmitError[field.getId()] = message

            if self.EnableDueDate():
                if due_date:
                    if not self.parseDueDate(due_date):
                        SubmitError['due_date'] = _("Invalid date")

            # this perhaps needs to be improved
            if SubmitError:
                page = self.ShowIssue
                REQUEST.set('change', 'Details')
                return page(REQUEST, SubmitError=SubmitError)


        # Section must be a list and might only allow for recognized values
        if sections is not None:
            if not isinstance(sections, list):
                sections = [sections]

            sections = [unicodify(x) for x in sections]

            if not self.CanAddNewSections():
                # check that all sections are recognized
                _options = self.getSectionOptions()
                for section in sections:
                    assert section in _options
            # set it
            if self.sections != sections:
                change['sections'] = dict(old=self.sections, new=sections)
            self.sections = sections

        # Type must be recognized
        if type is not None: ## I hate this variable name!
            assert type in self.getTypeOptions(), "Unrecognized issue type"

            # set it
            if self.type != type:
                change['type'] = dict(old=self.type, new=type)
            self.type = type

        # urgency must be recognized
        if urgency is not None:
            assert urgency in self.getUrgencyOptions(), "Unrecognized issue urgency"

            # set it
            if self.urgency != urgency:
                change['urgency'] = dict(old=self.urgency, new=urgency)
            self.urgency = urgency

        # due_date must be a valid date
        if self.EnableDueDate() and due_date is not None:
            if due_date or self.getDueDate():
                if due_date:
                    due_date = self.parseDueDate(due_date)
                    assert due_date is not None, "Invalid due date"
                else:
                    due_date = None

                if due_date != self.getDueDate():
                    change['due_date'] = dict(old=self.getDueDate(), new=due_date)
                assert due_date is None or hasattr(due_date, 'strftime'), repr(due_date)
                self.due_date = due_date

        # because of the way forms work, the confidential boolean is never
        # present as False, so we have to assume that it is default.
        # That means that an issue being confidential is always set in
        # this method.
        # niceboolean() asserts we're returning a True or False
        confidential = Utils.niceboolean(confidential)
        if confidential != self.confidential:
            change['confidential'] = dict(old=self.confidential, new=confidential)
        self.confidential = confidential

        if url2issue is not None:
            url2issue = url2issue.strip()
            if self.url2issue != url2issue:
                change['url2issue'] = dict(old=self.url2issue, new=url2issue)
            self.url2issue = url2issue

        if self.UseEstimatedTime() and estimated_time_hours is not None:
            hours = self._parseTimeHours(estimated_time_hours)
            assert isinstance(hours, float)

            # initially self.estimated_time_hours will be None. And if the
            # input estimated_time_hours is left blank then there is no change.
            # However if this is the second time
            if hours != self.estimated_time_hours and estimated_time_hours:
                change['estimated_time_hours'] = dict(old=self.estimated_time_hours,
                                                      new=hours)
            if estimated_time_hours:
                self.estimated_time_hours = hours
            elif self.estimated_time_hours is not None:
                # if it was something before and this time the user has wiped
                # it then this needs to be set back to None
                self.estimated_time_hours = None

        if self.UseActualTime() and actual_time_hours is not None:
            hours = self._parseTimeHours(actual_time_hours)
            assert isinstance(hours, float)

            if hours != self.actual_time_hours and actual_time_hours:
                change['actual_time_hours'] = dict(old=self.actual_time_hours,
                                                   new=hours)
            if actual_time_hours:
                self.actual_time_hours = hours
            elif self.actual_time_hours is not None:
                self.actual_time_hours = None

        if REQUEST is not None:
            # we can save custom fields
            for field in self.getCustomFieldObjects():
                old_data = self.getCustomFieldData(field.getId())
                self.setCustomFieldData(field, field.getId(), REQUEST.get(field.getId()))
                new_data = REQUEST.get(field.getId())
                if new_data is not None and not \
                  compare_custom_value(old_data, new_data, field.getPythonType()):
                    change[field.getId()] = dict(old=field.showValue(old_data),
                                                 new=field.showValue(new_data))

        if change:

            # something has changed in the issue!
            change['change_date'] = DateTime()
            issueuser = self.getIssueUser()
            cmfuser = self.getCMFUser()
            zopeuser = self.getZopeUser()
            email = fromname = None

            if self.has_cookie(self.getCookiekey('email')):
                email = self.get_cookie(self.getCookiekey('email'))
            if self.has_cookie(self.getCookiekey('name')):
                fromname = self.get_cookie(self.getCookiekey('name'))

            if issueuser:
                change['acl_adder'] = ','.join(issueuser.getIssueUserIdentifier())
                fromname = issueuser.getFullname()
                email = issueuser.getEmail()

            elif zopeuser:
                path = '/'.join(zopeuser.getPhysicalPath())
                name = zopeuser.getUserName()
                change['acl_adder'] = ','.join([path, name])

            if email:
                change['email'] = email
            if fromname:
                change['fromname'] = fromname

            self._addDetailChange(change)

        self._updateModifyDate()
        # things have changed, so update its index
        self.reindex_object()

        if REQUEST is not None:
            # go back to the issue itself
            REQUEST.RESPONSE.redirect(self.absolute_url())

    def increment_issue_actual_time(self, followupobject):
        assert followupobject.getActualTimeHours()
        assert self.UseFollowupActualTime()
        assert self.UseActualTime()

        issue_hours = self.getActualTimeHours()
        if not issue_hours:
            issue_hours = 0.0
        issue_hours += followupobject.getActualTimeHours()
        self.actual_time_hours = issue_hours

    def isCreator(self):
        """ return true if the current user is logged in as the same user
        who created this issue. """

        issueuser = self.getIssueUser()
        if issueuser:
            identifier = issueuser.getIssueUserIdentifier()
            identifier = ','.join(identifier)
            acl_adder = self.getACLAdder()
            return identifier == acl_adder

        return False


    def getCameFromSearchURL(self):
        """ if the previous page was a search, return the URL back to the same """
        raise NotImplementedError, "This method has be deprecated"

        referer = self.REQUEST.get('HTTP_REFERER')
        if not referer:
            return None

        if referer.find(self.getRootURL()) == -1:
            return None

        if referer.find('?') > -1 and referer.split('?')[1].find('q') > -1:
            querystring = referer.split('?')[1]
            qs = cgi.parse_qs(querystring)
            if qs.has_key('q'):
                #q = qs.get('q')[0]
                return referer


        return None

    def getCameFromReportURL(self):
        """ if the previous page the user was on was a report,
        return the URL to that report. If it wasn't or the report can't be found
        return None.

        This is used on the ShowIssue page so that we can link back to the
        report they came from.
        """
        raise NotImplementedError, "This method has be deprecated"

        referer = self.REQUEST.get('HTTP_REFERER')
        if not referer:
            return None


        if referer.find('/report-') > -1 and referer.startswith(self.getRootURL()):
            regex = r'/report-(.*?)$'
            found = re.findall(regex, referer)
            if found:
                reportid = found[0]
                container = self.getReportsContainer()
                if hasattr(container, reportid):
                    root_url = self.getRoot().absolute_url_path()
                    if root_url == '/':
                        root_url = ''
                    return '%s/%s/report-%s' % (root_url, self.whichList(), reportid)

        return None


    ##
    ## Drafts for followups
    ##


    def getMyThreadDrafts(self, issueid=None):
        """ return a list of issuethread draft objects """
        if not self.SaveDrafts(): # don't even bother
            return []

        ids = self._getDraftThreadIds()
        if not ids:
            return []

        container = self.getDraftsContainer()
        objects = []
        for id in ids:
            if hasattr(container, id):
                object = getattr(container, id)
                if object.meta_type == ISSUETHREAD_DRAFT_METATYPE:
                    if issueid is None or object.issueid == issueid:
                        objects.append(object)

        return objects

    # Commented out because this is already happening in IssueTracker.py
    #def _getDraftThreadIds(self, separate=False, include_current=True):
    #    """ return the possible draft ids we have """
    #    c_key = self.getCookiekey('draft_followup_ids')
    #    c_key = self.defineInstanceCookieKey(c_key)
    #    ids_cookie = self.get_cookie(c_key, '')
    #    ids_cookie = [x.strip() for x in ids_cookie.split('|') if x.strip()]
    #
    #    issueuser = self.getIssueUser()
    #    ids_user = []
    #    if issueuser:
    #        container = self.getDraftsContainer()
    #        all_draftobjects = container.objectValues(ISSUETHREAD_DRAFT_METATYPE)
    #        acl_adder = ','.join(issueuser.getIssueUserIdentifier())
    #        for draft in all_draftobjects:
    #            if draft.getACLAdder()==acl_adder:
    #                ids_user.append(draft.getId())
    #
    #
    #    if separate:
    #        return Utils.uniqify(ids_cookie), Utils.uniqify(ids_user)
    #    else:
    #        return Utils.uniqify(ids_cookie+ids_user)


    security.declareProtected('View', 'DeleteDraftIssue')
    def DeleteDraftThread(self, id, REQUEST=None):
        """ delete this id from issue user or cookies and delete the
        draft issue object. """
        ids_cookie, ids_user = self._getDraftThreadIds(separate=True)
        matched = False

        if id in ids_cookie:
            matched = True
            ids_cookie.remove(id)
            # save this
            c_key = self.getCookiekey('draft_followup_ids')
            c_key = self.defineInstanceCookieKey(c_key)
            all_draft_ids = '|'.join(ids_cookie)
            self.set_cookie(c_key, all_draft_ids, days=14)

        issueuser = self.getIssueUser()
        if id in ids_user and issueuser:
            matched = True

        if matched:
            # mark the draft issue as obsolete
            container = self.getDraftsContainer()
            container.manage_delObjects([id])

        if REQUEST is not None:
            url = self.absolute_url()
            REQUEST.RESPONSE.redirect(url)


    def _dropDraftThread(self, id):
        """ remove this draft issuethread object if it exists """
        container = self.getDraftsContainer()

        # remove potential client cookie
        ids_cookie, ids_user = self._getDraftThreadIds(separate=True)
        issueuser = self.getIssueUser()
        if id in ids_cookie:
            ids_cookie.remove(id)
            all_draft_ids = '|'.join(ids_cookie)
            c_key = self.getCookiekey('draft_followup_ids')
            c_key = self.defineInstanceCookieKey(c_key)
            self.set_cookie(c_key, all_draft_ids, days=14)

        # remove draft object
        if hasattr(container, id):
            container.manage_delObjects([id])

    def _dropMatchingDraftThreads(self, thread):
        """ delete (if any) all thread drafts that match this particular
        followup thread object. """
        title = thread.getTitle()
        comment = thread.getComment()

        container = self.getDraftsContainer()

        # the requirement for matching what to delete is if a draft matches
        # either:
        #   - exactly on title and comment
        #   - exactly on title, starts on comment
        for draft in container.objectValues(ISSUETHREAD_DRAFT_METATYPE):
            if not draft.getTitle() or not draft.getComment(): # odd draft!
                continue

            draft_title = unicodify(draft.getTitle())
            draft_comment = unicodify(draft.getComment())
            if draft_title == title and draft_comment == comment:
                self._dropDraftThread(draft.getId())
            elif comment.startswith(draft_comment) and draft_title == title:
                self._dropDraftThread(draft.getId())



    security.declareProtected('View', 'SaveDraftThread')
    def SaveDraftThread(self, REQUEST, draft_followup_id=None,
                       prevent_preview=True,
                       *args, **kw):
        """ basically just show AddIssue again except that we
        save a draft on the side. """
        if prevent_preview:
            REQUEST.set('previewissue', False)

        if self.SaveDrafts() and \
               (\
                 (draft_followup_id is None and self._reason2saveDraft(REQUEST)) \
                 or \
                 draft_followup_id is not None \
               ):
            action = REQUEST.get('action','')
            issueid = self.getId()
            draft_followup_id = self._saveDraftThread(issueid, action, REQUEST, draft_followup_id)
            kw['draft_followup_id'] = draft_followup_id
            kw['draft_saved'] = True
        return self.index_html(REQUEST, *args, **kw)


    security.declareProtected('View', 'AutoSaveDraftThread')
    def AutoSaveDraftThread(self, REQUEST, draft_followup_id=None,
                       *args, **kw):
        """ Called by the Ajax script. Return the draft_followup_id that
        we create if so."""


        if self.SaveDrafts() and \
               (\
                 (not draft_followup_id and self._reason2saveDraft(REQUEST)) \
                 or \
                 draft_followup_id \
               ):
            action = REQUEST.get('action','')
            issueid = self.getId()
            draft_followup_id = self._saveDraftThread(issueid, action, REQUEST, draft_followup_id, is_autosave=True)
            return draft_followup_id
        else:
            return ""


    def getRecentOtherDraftThreadAuthor(self, only_fromname=False, max_age_seconds=20,
                                        min_timestamp=None, REQUEST=None):
        """ return the name of the author of the most recent draft followup
        that is not written by the current user.
        """
        you_fromname = self.getSavedUser('fromname')
        you_email = self.getSavedUser('email')
        now = int(DateTime())

        if REQUEST is not None:
            ct = 'text/html; charset=%s' % UNICODE_ENCODING
            REQUEST.RESPONSE.setHeader('Content-Type', ct)
            self.StopCache()

        container = self.getDraftsContainer()
        draftobjects = [x for x in container.objectValues(ISSUETHREAD_DRAFT_METATYPE)
                                if x.getIssueId()==self.getIssueId()]

        if min_timestamp:
            # the @min_timestamp is possibly an integer timestamp of how old
            # the drafts have to be to be considered "recent".
            # Usually min_timestamp is set by the page template code which the
            # javascript picks up and sticks to. Then this timestamp is effectively
            # when the page was generate and thus the time the user came to it.
            draftobjects = [x for x in draftobjects if int(x.getModifyDate()) > int(min_timestamp)]

        draftobjects.sort(lambda x,y: cmp(y.getModifyDate(), x.getModifyDate()))

        fmt_followup = u"%s is working on a followup"
        for draft in draftobjects:
            if now - int(draft.getModifyDate()) > max_age_seconds:
                return None
            if draft.getFromname() != you_fromname and draft.getEmail() != you_email:

                if only_fromname and draft.getFromname():
                    return fmt_followup % draft.getFromname()
                elif only_fromname and draft.getEmail():
                    return fmt_followup % draft.getEmail()
                elif draft.getFromname() or draft.getEmail():
                    if draft.getFromname() and draft.getEmail():
                        name = self.ShowNameEmail(draft.getFromname(), draft.getEmail())
                    elif draft.getFromname():
                        name = draft.getFromname()
                    else:
                        name = draft.getEmail()
                    return fmt_followup % name
        return None

    def getRecentOtherDraftThreadAuthorFast(self, min_timestamp=None,
                                            max_age_seconds=40, REQUEST=None):
        """ return the name of the author of the most recent draft followup or None
        """
        # XXX: Needs a unit test with decent coverage
        template = u"%s is working on a followup"
        try:
            draft = self._v_recent_draft
            if max_age_seconds:
                if int(DateTime()) - int(draft.getModifyDate()) > max_age_seconds:
                    return None
            if min_timestamp:
                if int(draft.getModifyDate()) < int(min_timestamp):
                    return None

            no_words = len(draft.comment.split())
            if not no_words:
                return None

            fromname = draft.getFromname(issueusercheck=False)
            if fromname:
                you_fromname = self.getSavedUser('fromname')
                if fromname != you_fromname:
                    msg =  template % fromname
                    if no_words == 1:
                        msg += " (1 word)"
                    else:
                        msg += " (%s words)" % no_words
                    return msg

        except AttributeError:
            # it has simply not been set. Very common
            pass

        # default is to return None


    def getRecentOtherDraftThreadAuthor_json(self,
                                             only_fromname=False,
                                             max_age_seconds=20,
                                             min_timestamp=None,
                                             REQUEST=None):
        """JSON wrapper on getRecentOtherDraftThreadAuthor()
        Returns either {} or {'msg':'Something'}
        """
        msg = self.getRecentOtherDraftThreadAuthorFast(max_age_seconds=max_age_seconds,
                                                       min_timestamp=min_timestamp)
        if REQUEST is not None:
            REQUEST.RESPONSE.setHeader('Content-Type', 'application/javascript')

        if msg:
            r = dict(msg=msg)
        else:
            r = dict()

        if simplejson:
            return simplejson.dumps(r)
        else:
            return repr(r)

    def getLatestDraftThreadAuthor(self, only_if_not_you=False):
        """ return the fullname of the latest draft thread author.

        If @only_if_not_you is true, then don't bother if the current
        user *is* the latest draft thread author.
        """
        latest_draft = self._getLatestThreadDraft()

        if only_if_not_you:
            you_fromname = self.getSavedUser('fromname')
            you_email = self.getSavedUser('email')

        if latest_draft is not None:
            fromname = latest_draft.getFromname()
            email = latest_draft.getEmail()
            if only_if_not_you:
                if you_fromname == fromname and you_email == email:
                    return ''
                else:
                    return self.ShowNameEmail(fromname, email)
            else:
                return self.ShowNameEmail(fromname, email)
        return ''


    def _reason2saveDraft(self, request):
        """ no draft has been created. Inspect this 'request' see if
        there is reason enough to save a draft. """

        enough_request_data = False
        for key in ('comment',):
            if Utils.SimpleTextPurifier(request.get(key,'')):
                enough_request_data = True
                break

        if enough_request_data:
            # check that a draft like this doesn't exist already
            _finder = self._findMatchingThreadDraft
            draft = _finder(request.get('comment',''))
            if draft:
                return False

        return enough_request_data

    def _findMatchingThreadDraft(self, comment):
        """ return drafts that match exactly. Return None if nothing found """
        container = self.getDraftsContainer()
        draftobjects = container.objectValues(ISSUETHREAD_DRAFT_METATYPE)
        for draft in draftobjects:
            if unicodify(draft.comment) == comment:
                return draft
        return None

    def _getLatestThreadDraft(self):
        """ return the thread draft object that is the latest """
        container = self.getDraftsContainer()
        draftobjects = list(container.objectValues(ISSUETHREAD_DRAFT_METATYPE))
        draftobjects.sort(lambda x,y: cmp(y.getModifyDate(), x.getModifyDate()))
        try:
            return draftobjects[0]
        except IndexError:
            return None


    def _saveDraftThread(self, issueid, action, REQUEST, draft_followup_id=None,
                         is_autosave=False):
        """ return the id this created """
        draftscontainer = self.getDraftsContainer()
        if draft_followup_id:
            if not hasattr(draftscontainer, draft_followup_id):
                # you're lying!
                draft_followup_id = None

        if not draft_followup_id:
            # need to create a draft issuethread object
            _prefix = 'thread-%s-'%issueid # use the issue we're in as prefix
            id = self.generateID(5, prefix=_prefix,
                                 meta_type=ISSUETHREAD_DRAFT_METATYPE,
                                 incontainer=draftscontainer
                                 )
            # create a draft issue
            draftthread = self._createDraftThread(id, issueid, action)
            draft_followup_id = id
        else:
            draftthread = getattr(draftscontainer, draft_followup_id)

        issueuser = self.getIssueUser()
        acl_adder = None
        if issueuser:
            acl_adder = ','.join(issueuser.getIssueUserIdentifier())

        # now, populate this draftissue with as much data as
        # we can find
        modifier = draftthread.ModifyThread
        rget = REQUEST.get

        # only modify the thread draft if comment, fromname or email has changed
        if draftthread.comment == rget('comment') and draftthread.fromname == rget('fromname') \
          and draftthread.email == rget('email'):
            # the thread hasn't changed enough, no need to call ModifyThread()
            # again which would be a waste of ZODB transactions and would also
            # mean that the getModifyDate() of the draft thread would be
            # set again.
            return draft_followup_id

        modifier(title=rget('title'),
                 comment=rget('comment'),
                 fromname=rget('fromname'),
                 email=rget('email'),
                 acl_adder=acl_adder,
                 display_format=rget('display_format', self.getSavedTextFormat()),
                 actual_time_hours=rget('actual_time_hours'),
                 is_autosave=is_autosave,
                 )

        self._v_recent_draft = draftthread

        # remember this
        issueuser = self.getIssueUser()
        if not issueuser:
            # stick this in a cookie
            c_key = self.getCookiekey('draft_followup_ids')
            c_key = self.defineInstanceCookieKey(c_key)
            all_draft_ids = self._getDraftThreadIds()
            if draft_followup_id not in all_draft_ids:
                all_draft_ids.append(draft_followup_id)
                all_draft_ids = '|'.join(all_draft_ids)
                self.set_cookie(c_key, all_draft_ids, days=14)

            # also save, the name if we didn't already have it
            if rget('fromname') and not self.getSavedUser('fromname', use_request=False):
                self.set_cookie(self.getCookiekey('name'), rget('fromname'))
            if rget('email') and not self.getSavedUser('email', use_request=False):
                self.set_cookie(self.getCookiekey('email'), rget('email'))

        return draft_followup_id




    def _createDraftThread(self, id, issueid, action):
        """ create a draftissuethread and return it """
        root = self.getDraftsContainer()

        title = None
        if action.lower() == 'AddFollowup'.lower():
            title = _("Followup")
        else:
            title = action

        inst = IssueTrackerDraftIssueThread(id, issueid, action, title=title)
        root._setObject(id, inst)
        object = root._getOb(id)
        return object



    ## Changing the issue in mid-air


    def Others2Notify(self, format='email', emailtoskip=None, requireemail=False,
                      do=None # legacy parameter
                      ):
        """
        Returns a list of names and emails of people to notify if this issue
        changes or gets a followup.
        Take the hide_me and confidential factor into consideration.

        if format == email:
            return [foo@bar.com, bar@foo.com,...]
        elif format == name:
            return [Foo, Bar, ...]
        elif format == both:
            return ['Foo <foo@bar.com>', ...]
        elif format == merged:
            return [self.ShowNameEmail(Foo, foo@bar.com),...]

        """

        if emailtoskip is None:
            # caller was lazy not to specify this
            # we do it here in the code
            issueuser = self.getIssueUser()
            if issueuser:
                emailtoskip = issueuser.getEmail()
            elif self.REQUEST.get('email'):
                emailtoskip = self.REQUEST.get('email')
            elif self.has_cookie(self.getCookiekey('email')):
                emailtoskip = self.get_cookie(self.getCookiekey('email'))

        all = []
        nameemailshower = lambda n,e: self.ShowNameEmail(n, e, highlight=0)

        names_and_emails = self._getOthers(emailtoskip)
        for _name, _email in names_and_emails:
            add = ''
            if emailtoskip is not None and ss(_email) == ss(emailtoskip):
                continue # skip it!

            if requireemail and not Utils.ValidEmailAddress(_email):
                continue # skip it!

            if format == 'tuple':
                add = (_email, nameemailshower(_name and _name or _email, _email))
            elif format == 'email':
                add = _email or _name
            elif format == 'name':
                add = _name or _email
            else:
                if _name and _email:
                    if format == 'both':
                        add = "%s <%s>"%(_name, _email)
                    else:
                        add = nameemailshower(_name, _email)
                elif _name:
                    if format == 'both':
                        add = _name
                    else:
                        add = _name
                elif _email:
                    if format == 'both':
                        add = _email
                    else:
                        add = nameemailshower(_email, _email)
            if add and add not in all:
                all.append(add)

        return all


    def _getOthers(self, avoidemail=None):
        """ return a 2D list of names and emails that _should_ be notified """
        all = []        # what we will return
        allemails = {}  # avoid duplicates

        # 1. The issue at hand.
        # proceed only if Manager or open-name on the issue
        if self.hasManagerRole() or not self.hide_me:
            # self.email is the email of the thread
            # emailtoskip comes from the param/cookie if applicable
            issue_email = self.getEmail()
            if issue_email and issue_email != avoidemail:
                issue_fromname = self.getFromname()
                item = [issue_fromname, issue_email]
                all.append(item)
                allemails[ss(issue_email)] = 1

        # 2. All authors of followups/threads
        for thread in self.objectValues(ISSUETHREAD_METATYPE):
            thread_email = thread.getEmail()
            if thread_email and thread_email != avoidemail:
                ss_thread_email = ss(thread_email)
                if not allemails.has_key(ss_thread_email):
                    thread_fromname = thread.getFromname()
                    item = [thread_fromname, thread_email]
                    all.append(item)
                    allemails[ss_thread_email] = 1


        # 3. Get all subscribers
        notifyables = self.getNotifyablesEmailName()
        for subscriber in self.getSubscribers():

            if notifyables.has_key(subscriber):
                #       Name                     Email
                item = [notifyables[subscriber], subscriber]
                ss_subscriber = ss(subscriber)
                if not allemails.has_key(ss_subscriber):
                    all.append(item)
                    allemails[ss_subscriber] = 1

            elif len(subscriber.split(','))==2:
                # quite possibly an acl user
                ufpath, name = subscriber.split(',')
                try:
                    uf = self.unrestrictedTraverse(ufpath)
                except KeyError:
                    continue
                if uf.meta_type == ISSUEUSERFOLDER_METATYPE:
                    issueuserobj = uf.data[name]
                    ss_email = ss(issueuserobj.getEmail())
                    if not allemails.has_key(ss_email):
                        item = [issueuserobj.getFullname(),
                                issueuserobj.getEmail()]
                        all.append(item)
                        allemails[ss_email] = 1


            elif Utils.ValidEmailAddress(subscriber):
                ss_subscriber = ss(subscriber)
                if not allemails.has_key(ss_subscriber):
                    all.append(['', subscriber])
                    allemails[ss_subscriber] = 1


        del allemails
        return all

    def getOptionButtons(self):
        """ Return list of dicts of actions and verbs """
        res=[]

        def url_quote_unicodeaware(s):
            # if the string is a unicode string,
            # first convert it to a non-unicode string
            # then apply url_quote.
            if isinstance(s, unicode):
                return Utils.url_quote(s.encode(UNICODE_ENCODING))
            else:
                return Utils.url_quote(s)

        issuestatus = self.status.lower()
        for item in self.getStatusesMerged(aslist=1):
            status, verb = item
            if issuestatus != status.lower():
                action = verb.capitalize()
                action_quoted = url_quote_unicodeaware(action)

                #res.append([action, verb.capitalize()])
                res.append({'action':action, 'verb':verb.capitalize(),
                            'action_quoted':action_quoted})

        res.append({'action':u'Delete', 'verb':u'Delete',
                    'action_quoted':url_quote_unicodeaware('Delete'),
                    'id':'delete_option_button'})

        return res

    def StatusByWhom(self):
        """ return who was responsible for the latest status this issue has """
        threads = self.ListThreads()
        if threads:
            last_thread = threads[-1]
            fromname = last_thread.getFromname()
            if not fromname:
                fromname = last_thread.getEmail()
            status = self.status.capitalize()
            return "%s by %s" % (status, fromname)
        else:
            fromname = self.getFromname()
            if not fromname:
                fromname = self.getEmail()
            return "Added by %s" % fromname


    def getBriefedDescription(self, length=100):
        """ return some of the text """
        hq = self.HighlightQ # shortcut

        description = self.getDescriptionPure()
        if len(description) <= length:
            d = description
        elif description.strip().find(' ') == -1:
            d = description[:length].strip()
        else:
            try:
                description = description[:length].strip()
                while description[-1] not in [' ','\n']:
                    description = description[:-1]
                d = description + '...'
            except:
                d = description[:length]

        if isinstance(d, str):
            return self.HighlightQ(Utils.html_entity_fixer(Utils.safe_html_quote(d)))
        else:
            return self.HighlightQ(Utils.safe_html_quote(d))


    def showAdditionalInformation(self, usebrackets=0, timedifference=None):
        """ returns a string of information about the issue.
        Zeroth (if timedifference is not None) the time difference
        First isConfidential,
        Second # files
        Third # comments
        """
        info = []
        if timedifference is not None:
            if timedifference:
                info.append(str(timedifference))

        if self.isConfidential():
            info.append("confidential")

        count_files = self.countFileattachments()
        if count_files:
            if count_files == 1:
                info.append('%s file'%count_files)
            else:
                info.append('%s files'%count_files)

        count_comments = self.countThreads()
        if count_comments:
            if count_comments == 1:
                info.append('%s comment'%count_comments)
            else:
                info.append('%s comments'%count_comments)

        assignments = self.getAssignments()
        if assignments:
            try:
                if assignments[-1].getState() == 1:
                    _name = assignments[-1].getAssigneeFullname()
                    _email = assignments[-1].getAssigneeEmail()
                    if _name or _email:
                        info.append('assigned to %s' % self.ShowNameEmail(_name, _email, highlight=False))
                    else:
                        info.append('assigned')

                elif assignments[-1].getState() == 0:
                    _name = assignments[-1].getAssigneeFullname()
                    _email = assignments[-1].getAssigneeEmail()
                    if _name or _email:
                        info.append('reassigned to %s' % self.ShowNameEmail(_name, _email, highlight=False))
                    else:
                        info.append('reassigned')
            except AttributeError:
                pass

        if info:
            if usebrackets:
                return "(%s)"%(', '.join(info))
            else:
                return ', '.join(info)
        else:
            return ""


    def hasThreads(self):
        """ return true if there are issuethreads within """
        return not not self.ListThreads()

    def countThreads(self):
        """ return the number of threads within """
        return len(self.ListThreads())

    def getThreadObjects(self):
        """ Return the followup objects. The threads. """
        return self.objectValues(ISSUETHREAD_METATYPE)
    listThreads = ListThreads = getThreadObjects # better name

    def getLastThread(self):
        """ Return the last thread in an issue or None """
        allthreads = self.ListThreads()
        if allthreads:
            return allthreads[-1]
        else:
            return None

    def countFileattachments(self):
        """ return [no files in issue, no files in threads] """
        return len(self.ZopeFind(self, obj_metatypes=['File'], search_sub=1))

    def filenames(self):
        """ return all the filenames of this issue splitted """
        files = self.objectValues('File')
        all = []
        for file in files:
            all.extend(Utils.filenameSplitter(file.getId()))
        return Utils.uniqify([x.lower() for x in all])


    def manage_beforeDelete(self, REQUEST=None, RESPONSE=None):
        """ uncatalog yourself """
        for thread in self.objectValues(ISSUETHREAD_METATYPE):
            thread.unindex_object()
        self.unindex_object()

    def index_object(self, idxs=None):
        """A common method to allow Findables to index themselves."""
        path = '/'.join(self.getPhysicalPath())
        catalog = self.getCatalog()

        if idxs is None:
            # because I don't want to put mutable defaults in
            # the keyword arguments
            idxs = ['id','title','description', 'fromname','email','url2issue',
                    'meta_type','status','path','modifydate',
                    'filenames','issuedate',
                    'urgency','type']
        else:
            # No matter what, when indexing you must always include 'path'
            # otherwise you might update indexes without putting the object
            # brain in the catalog. If that happens the object won't be
            # findable in the searchResults(path='/some/path') even if it's
            # findable on other indexes such as comment.

            if 'path' not in idxs:
                idxs.append('path')

        indexes = catalog._catalog.indexes

        # this test is really old
        #if 'status' in idxs and not indexes.has_key('status'):
        #    idxs.remove('status')

        for idx in ('modifydate','issuedate','urgency','type'):
            if idx in idxs and not indexes.has_key(idx):
                msg = "%s Catalog out of date. " % self.getRoot().absolute_url()
                msg += "Missing '%s'. Press the Update Everything button" % idx
                warnings.warn(msg)
                idxs.remove(idx)

        if self.EnableDueDate() and indexes.has_key('due_date'):
            idxs.append('due_date')

        catalog.catalog_object(self, path, idxs=idxs)

    def getTitle_idx(self):
        return self.getTitle()

    def getFromname_idx(self):
        return self.getFromname()

    def getDescription_idx(self):
        return self.getDescription()

    def unindex_object(self):
        """A common method to allow Findables to unindex themselves."""
        path = '/'.join(self.getPhysicalPath())
        self.getCatalog().uncatalog_object(path)

    def isImplicitlySubscribing(self, email):
        """ return if they're already involved in this issue such that there is
        no point for them becoming a subscriber """

        # was it you who added this issue?
        issue_email = self.getEmail()
        if email and issue_email == email:
            return True

        # have you made any kind of followup?
        for thread in self.ListThreads():
            if email and thread.getEmail() == email:
                return True

        return False # fallback

    def isSubscribing(self, email):
        """ check if in subscribers list """
        subscribers = self.getSubscribers()
        email = ss(str(email))
        return email in [ss(x) for x in subscribers]

    def getSubscribers(self):
        """ return subscribers list """
        return getattr(self, 'subscribers', [])

    def _addSubscriber(self, name_or_email):
        """ add subscriber to subscribers list """
        subscribers = self.getSubscribers()
        email = None
        name_or_email = name_or_email.strip()

        if Utils.ValidEmailAddress(name_or_email):
            email = name_or_email
        elif len(name_or_email.split(','))==2:
            # it's a acl user
            email = name_or_email
        else:
            # what we're adding is not an email,
            # expect it to be the name of a notifyable
            ss_name_or_email = ss(name_or_email)
            for notifyable in self.getNotifyables():
                if ss_name_or_email == ss(notifyable.getName()):
                    email = notifyable.getEmail()
                    break

        if email is not None:
            if not self.isSubscribing(email):
                if isinstance(subscribers, tuple):
                    subscribers = list(subscribers)
                subscribers.append(email)

                self.subscribers = subscribers
                return True

        return False

    def _delSubscriber(self, email):
        """ remove item from subscribers list """
        n_subscribers = []
        ss_email = ss(email)
        for subscriber in self.getSubscribers():
            if ss_email != ss(subscriber):
                n_subscribers.append(subscriber)
        self.subscribers = n_subscribers

    def Subscribe(self, subscriber, unsubscribe=0, REQUEST=None):
        """ analyse subscriber and add accordingly """

        if subscriber == 'issueuser':
            issueuser = self.getIssueUser()
            assert issueuser, "Not logged in as Issue User"
            identifier = issueuser.getIssueUserIdentifierString()
            if unsubscribe:
                self._delSubscriber(identifier)
            else:
                self._addSubscriber(identifier)
        else:

            emails = self.preParseEmailString(subscriber, aslist=1)
            for email in emails:
                if unsubscribe:
                    self._delSubscriber(email)
                else:
                    self._addSubscriber(email)

            # Exceptional case. If the user doesn't already have an email
            # address, but has asked to subscribe with only one email
            # address, then we can assume that that is the email address he wants
            # to use all the time.
            if not self.getSavedUser('email') and len(emails)==1:
                if Utils.ValidEmailAddress(emails[0]):
                    # add this
                    self.set_cookie(self.getCookiekey('email'), emails[0])


        if REQUEST is not None:
            url = self.absolute_url() + '/'
            REQUEST.RESPONSE.redirect(url)


    def getFriends(self, maxlength=13):
        """ find other people who use this issuetracker and return a list
        of dicts with keys 'name', 'email', 'show', 'notifyable'.
        Avoid assignment blacklisted people.
        Search current issue.
        Search local acl_folders if Issue User Folder.
        Search Adjacent issues and their threads.
        """
        friends = []
        friends_emails = []

        try:
            maxlength = abs(int(maxlength))
        except ValueError:
            maxlength = 13


        # 0. Who are you?
        issueuser = self.getIssueUser()
        if issueuser:
            _email_ss = Utils.ss(issueuser.getEmail())
        else:
            _email_ss = Utils.ss(self.getSavedUserEmail())

        if _email_ss:
            friends_emails.append(_email_ss)

        # 1. Search current issue
        if self.meta_type == ISSUE_METATYPE:
            _email = self.getEmail()

            if _email and Utils.ss(_email) not in friends_emails and Utils.ValidEmailAddress(_email):
                _email_ss = Utils.ss(_email)

                _name = self.getFromname()
                _show = self.ShowNameEmail(_name, _email, highlight=False)
                item = {'name':_name,
                        'email':_email,
                        'show':_show}
                friends.append(item)
                friends_emails.append(_email_ss)

            for thread in self.ListThreads():
                _email = thread.getEmail()
                _email_ss = Utils.ss(_email)
                if _email_ss not in friends_emails and Utils.ValidEmailAddress(_email):
                    _name = thread.getFromname()
                    _show = self.ShowNameEmail(_name, _email, highlight=False)
                    item = {'name':_name,
                            'email':_email,
                            'show':_show}
                    friends.append(item)
                    friends_emails.append(_email_ss)


        # 2. list of acl identifiers

        # filter=true removes all assignment blacklisted people
        all_users = self.getAllIssueUsers(filter=1)
        for each in all_users:
            user = each['user']
            _email = user.getEmail()
            _name = user.getFullname()
            _email_ss = Utils.ss(_email)
            _show = self.ShowNameEmail(_name, _email, highlight=False)
            if _email_ss not in friends_emails and Utils.ValidEmailAddress(_email):
                item = {'name':_name,
                        'email':_email,
                        'show':_show
                        }
                friends.append(item)
                friends_emails.append(_email_ss)


        # 3. all issues, all threads
        if len(friends) >= maxlength:
            issues = []
        else:
            issues = self.ListIssuesFiltered(skip_filter=True,
                                         keep_sortorder=False,
                                         sortorder='modifydate',
                                         reverse=False)

        for issue in issues:
            _email = issue.getEmail()
            _email_ss = Utils.ss(_email)
            if _email_ss not in friends_emails and Utils.ValidEmailAddress(_email):
                _name = issue.getFromname()
                _show = self.ShowNameEmail(_name, _email, highlight=False)
                item = {'name':_name,
                        'email':_email,
                        'show':_show}
                friends.append(item)
                friends_emails.append(_email_ss)

            for thread in self.ListThreads():
                _email = thread.getEmail()
                _email_ss = Utils.ss(_email)
                if _email_ss not in friends_emails:
                    _name = thread.getFromname()
                    _show = self.ShowNameEmail(_name, _email, highlight=False)
                    item = {'name':_name,
                            'email':_email,
                            'show':_show}
                    friends.append(item)
                    friends_emails.append(_email_ss)

            if len(friends) > maxlength:
                break

        friends = friends[:maxlength]

        # which email address can be replaced with a single name?
        all_notifyables = self.getNotifyables()
        emails2names = {}
        for noti in all_notifyables:

            emails2names[noti.getEmail()] = noti.getName()

        checked = []
        for friend in friends:
            if emails2names.has_key(friend['email']):
                #friend['show'] = emails2names.get(friend['email'])
                friend['notifyable'] = True
            else:
                friend['notifyable'] = False

            checked.append(friend)

        friends = checked

        return friends



    security.declareProtected('View', 'TellAFriend')
    def TellAFriend(self, email_string, friends=[], ignoreword='', added=False, send=True,
                    message_sender='', cancel=False):
        """ Allows people to send notifications to other people """

        if not self.UseTellAFriend():
            return "Tell a friend feature disabled"

        if cancel:
            self.REQUEST.RESPONSE.redirect(self.absolute_url())
            return

        email_string = email_string.strip()
        if (not email_string or email_string == ignoreword) and send:
            if not friends:
                self.REQUEST.RESPONSE.redirect(self.absolute_url())

        issueuser = self.getIssueUser()
        if issueuser:
            fromname = issueuser.getFullname()
            email = issueuser.getEmail()
        else:
            # look in cookies
            fromname = self.getSavedUserName()
            email = self.getSavedUserEmail()

        if fromname and Utils.ValidEmailAddress(email):
            fr = "%s <%s>"%(fromname, email)
        elif Utils.ValidEmailAddress(email):
            fr = email
        else:
            _f, _e = self.getSitemasterName(), self.getSitemasterEmail()
            fr = "%s <%s>"%(_f, _e)

        _roottitle = self.getRoot().getTitle()
        subject = "%s: An issue to your attention"%_roottitle


        if message_sender:
            msg = message_sender
        else:
            msg = self._constructTellAFriendMessage(fromname)


        if send:
            # first we need to figure out who to send to
            to = self.preParseEmailString(email_string, aslist=True)
            params = {}
            if self.REQUEST.get('NewIssue'):
                params['NewIssue'] = self.REQUEST.get('NewIssue')

            if to or friends:
                to_strings = [x.strip() for x in to]
                both = to_strings+friends

                both = ', '.join(both)
                #body = '\r\n'.join(['From: %s'%fr, 'To: %s'%both,
                #                'Subject: %s'%subject, "", msg])
                try:
                    self.sendEmail(msg, both, fr, subject, swallowerrors=False)
                    params['tellafriend'] = "Success. Message sent!"
                    params['good'] = 1
                except:
                    try:
                        err_log = self.error_log
                        err_log.raising(sys.exc_info())
                    except:
                        pass
                    LOG(self.__class__.__name__, PROBLEM, "Message could not be sent",
                        error=sys.exc_info())
                    params['tellafriend'] = "Failure. Message could not be sent"
                    params['bad'] = 1
                    try:
                        params.pop('NewIssue')
                    except AttributeError:
                        try:
                            params = Utils.dict_popper(params, 'NewIssue')[1]
                        except KeyError:
                            pass
                    except KeyError:
                        pass

            else:
                params['tellafriend'] = "Failed because no one to send to"
                params['bad'] = 1
                try:
                    params.pop('NewIssue')
                except AttributeError:
                    try:
                        params = Utils.dict_popper(params, 'NewIssue')[1]
                    except KeyError:
                        pass
                except KeyError:
                    pass

            url = self.absolute_url()

            if message_sender and len(message_sender) < 5000:
                params['message_sender'] = message_sender

            #params['MoreEmailOptions'] = 1
            url = Utils.AddParam2URL(url, params) + '#details'
            self.REQUEST.RESPONSE.redirect(url)

        else:
            return msg


    def _constructTellAFriendMessage(self, fromname):
        """ create a suggested TellAFriendMessage """
        _roottitle = self.getRoot().getTitle()
        br = '\r\n'
        if fromname:
            msg = fromname + " has asked you to have a look at an issue in %s " \
                  "with the following title:"%_roottitle + br
        else:
            msg = "You have been asked to have a look at an issue in %s "\
                  "with the following title:"%_roottitle + br

        _title = self.getTitle()
        if _title.find('"') > -1:
            msg += " '%s' "%_title
        else:
            msg += ' "%s" '%_title
        msg += 2*br + "The issue can be found at"+br
        msg += self.absolute_url()
        msg += 3*br

        # signature
        signature = self.showSignature()
        if signature:
            msg += "--" + br +signature

        return msg


    def getDefaultTellAFriendMessage(self, added=False):
        """ wrap TellAFriend() to be able to extract only the message """
        msg = self.TellAFriend('', added=added, send=False)
        return msg




    ## Issue Assignment

    security.declareProtected('View', 'changeAssignment')
    def changeAssignment(self, assignee, send_email=False):
        """ add a new assignee to the issue object only if the current assignee is the
        user who calls this. """
        if isinstance(send_email, basestring):
            send_email = Utils.niceboolean(send_email)

        assignments = self.getAssignments()
        lastone = assignments[-1]
        if lastone.isYou() or self.hasManagerRole():
            if not lastone.getACLAssignee() == assignee:
                self.createAssignment(assignee, state=0, send_email=send_email)

        url = self.absolute_url()
        self.REQUEST.RESPONSE.redirect(url)


    security.declareProtected('View', 'setAssignment')
    def setAssignment(self, assignee, send_email=False):
        """ add a new assignee to the issue object only if the current assignee is the
        user who calls this. """
        if isinstance(send_email, basestring):
            send_email = Utils.niceboolean(send_email)

        assignments = self.getAssignments()
        if assignments:
            state = 0
        else:
            state = 1

        if self.hasManagerRole():
            self.createAssignment(assignee, state=state, send_email=send_email)

        url = self.absolute_url()
        self.REQUEST.RESPONSE.redirect(url)


    def _getAssignments(self):
        """ return the issues assignment objects unsorted """
        return self.objectValues(ISSUEASSIGNMENT_METATYPE)


    def getAssignments(self, sort=True):
        """ return the issue assignment objects sorted """
        objects = self._getAssignments()
        if sort:
            objects = self.sortSequence(objects, (('assignmentdate',),))
        return objects

    def getFirstAssignment(self):
        """ return the first assignment or None """
        try:
            return self.getAssignments()[0]
        except IndexError:
            return None

    def getLastAssignment(self):
        """ return the last assignment or None """
        try:
            return self.getAssignments()[-1]
        except IndexError:
            return None


    def createAssignment(self, assignee_identifier, state=1,
                         send_email=False):
        """ create an Issue Assignment """
        request = self.REQUEST

        prefix = self.issueprefix + 'assignment'
        mtype = ISSUEASSIGNMENT_METATYPE
        id = self.generateID(4, prefix=prefix,
                             meta_type=mtype,
                             use_stored_counter=False)

        # check that the assignee_identifier exits
        try:
            userfolderpath, name = assignee_identifier.split(',')
        except ValueError:
            m = "Invalid assignee identifier (%s)"
            raise AssigneeNotFoundError, m % assignee_identifier

        userfolder = self.unrestrictedTraverse(userfolderpath)
        if name in userfolder.user_names():
            user = self.getIssueUserObject(assignee_identifier)
        else:
            m = "Invalid assignee identifier (%s)"
            raise AssigneeNotFoundError, m % assignee_identifier

        acl_adder = ''
        issueuser = self.getIssueUser()
        if issueuser:
            acl_adder = ','.join(issueuser.getIssueUserIdentifier())

        email_cookiekey = self.getCookiekey('email')
        name_cookiekey = self.getCookiekey('name')

        if issueuser and issueuser.getEmail():
            email = issueuser.getEmail()
        elif not request.get('email') and self.has_cookie(email_cookiekey):
            email = self.get_cookie(email_cookiekey)
        else:
            email = asciify(request.get('email',''), 'ignore')

        if issueuser and issueuser.getFullname():
            fromname = issueuser.getFullname()
        elif not request.get('fromname') and self.has_cookie(name_cookiekey):
            fromname = unicodify(self.get_cookie(name_cookiekey))
        else:
            fromname = unicodify(request.get('fromname',''))

        # Add it
        adder = self._createAssignmentObject
        assignment = adder(id, assignee_identifier, state,
                           fromname, email, acl_adder)

        if send_email and Utils.ValidEmailAddress(user.getEmail()) \
               and Utils.ss(user.getEmail()) != Utils.ss(email):
            self._sendAssignmentNotification(assignment, user.getEmail())


    def _createAssignmentObject(self, id, identifier, state,
                                fromname, email, acl_adder=None):
        """ create the actual Issue Assignment object """
        instance = IssueTrackerIssueAssignment(id, identifier, state,
                                               fromname, email,
                                               acl_adder)
        self._setObject(id, instance)
        assignment = self._getOb(id)

        return assignment

    def _sendAssignementEmail(self, to_name, to_email, from_name, from_email):
        """ Send a simple email to he who was assigned this issue """
        raise DeprecatedError, "We're using _sendAssignmentNotification() instead"


    def _sendAssignmentNotification(self, assignment, to_email):
        """ create a notification object about this new assignment object """
        # the person who "created" the assignment
        fromname = assignment.getFromname()
        email = assignment.getEmail()
        issue = aq_parent(aq_inner(assignment))

        notifyid = self.generateID(5, self.issueprefix+"notification",
                                   meta_type=NOTIFICATION_META_TYPE,
                                   use_stored_counter=False,
                                   incontainer=issue)

        title = issue.getTitle()
        issueID = issue.getId()
        date = DateTime()

        notification = IssueTrackerNotification(notifyid,
                             title, issue.getId(), [to_email],
                             assignment=assignment.getId()
                             )
        issue._setObject(notifyid, notification)
        notifyobject = getattr(issue, notifyid)
        if self.doDispatchOnSubmit():
            if 1: #try:
                self.dispatcher([notifyobject])
            else: #except:
                try:
                    err_log = self.error_log
                    err_log.raising(sys.exc_info())
                except:
                    pass
                LOG(self.__class__.__name__, PROBLEM,
                   'Email could not be sent', error=sys.exc_info())




    ##
    ## The issue's notifications
    ##


    def getCreatedNotifications(self, sort=False):
        objects = list(self._getCreatedNotifications())
        if sort:
            objects.sort(lambda x, y: cmp(x.date, y.date))
        return objects

    def _getCreatedNotifications(self):
        return self.objectValues(NOTIFICATION_META_TYPE)

    ##
    ## Misc.
    ##

    def getNotifiedUsersByNotificationsAndAssignment(self):
        """ return a list of of strings of people who will be notified
        when this issue was submitted. """

        strings = []
        _all_emails = []
        notifications = self.getCreatedNotifications()
        first_assignment = self.getFirstAssignment()

        if first_assignment is not None:
            assignee_name = first_assignment.getAssigneeFullname()
            assignee_email = first_assignment.getAssigneeEmail()
            add = self.ShowNameEmail(assignee_name, assignee_email, highlight=False)
            strings.append(add)
            _all_emails.append(assignee_email.lower())

        always = self.getAlwaysNotify()
        checked = [self._checkAlwaysNotify(x, format='list') for x in always]
        # checked is a list of tuples that look like this:
        # [(True, ['', 'peterbe@gmail.com']), ...]
        # And this can be used to help us figure out the names of the emails
        # stored in the notification objects.
        emails2names = {}

        for valid, name_email in checked:
            if not valid:
                continue

            n, e = name_email

            if n:
                emails2names[e.lower()] = n.strip()

        for notification in notifications:
            for email in notification.getEmails():
                name = emails2names.get(email.lower(), '')
                add = self.ShowNameEmail(name, email, highlight=False)
                if email.lower() not in _all_emails:
                    strings.append(add)
                    _all_emails.append(email.lower())

        return strings

    ##
    ## Notes
    ##

    def getNotes(self):
        """return all note objects"""
        return self.objectValues(ISSUENOTE_METATYPE)

    def getYourNotes(self, threadID=None):
        # first figure out if there are any notes in the issue
        # before we figure out who we can and search for them
        # properly.
        # The reason for this is that
        any_notes = False
        for __ in self.findNotes(threadID=threadID):
            any_notes = True
            break

        note_objects = []

        # before we fetch all private notes, just check that there are any
        # before we start the expensive operation of figuring out your
        # identifier and doing the search
        if any_notes:
            acl_adder = ''
            issueuser = self.getIssueUser()
            cmfuser = self.getCMFUser()
            zopeuser = self.getZopeUser()
            if issueuser:
                acl_adder = ','.join(issueuser.getIssueUserIdentifier())
            elif zopeuser:
                path = '/'.join(zopeuser.getPhysicalPath())
                name = zopeuser.getUserName()
                acl_adder = ','.join([path, name])

            ckey = self.getCookiekey('name')
            if issueuser and issueuser.getFullname():
                fromname = issueuser.getFullname()
            elif cmfuser and cmfuser.getProperty('fullname'):
                fromname = cmfuser.getProperty('fullname')
            elif self.has_cookie(ckey):
                fromname = self.get_cookie(ckey)
            else:
                fromname = ''

            ckey = self.getCookiekey('email')
            if issueuser and issueuser.getEmail():
                email = issueuser.getEmail()
            elif cmfuser and cmfuser.getProperty('email'):
                email = cmfuser.getProperty('email')
            elif self.has_cookie(ckey):
                email = self.get_cookie(ckey)
            else:
                email = ''

            if acl_adder:
                note_objects += list(self.findNotes(acl_adder=acl_adder,
                                                    threadID=threadID))
            elif email and fromname:
                note_objects += list(self.findNotes(fromname=fromname,
                                                    email=email,
                                                    threadID=threadID))

        note_objects.sort(lambda x,y: cmp(x.notedate, y.notedate))

        return note_objects



    security.declareProtected('View', 'createNote')
    def createNote(self, comment, public=False, threadID='',
                   REQUEST=None):
        """create a note via the web"""

        acl_adder = ''
        issueuser = self.getIssueUser()
        cmfuser = self.getCMFUser()
        zopeuser = self.getZopeUser()
        if issueuser:
            acl_adder = ','.join(issueuser.getIssueUserIdentifier())
        elif zopeuser:
            path = '/'.join(zopeuser.getPhysicalPath())
            name = zopeuser.getUserName()
            acl_adder = ','.join([path, name])

        ckey = self.getCookiekey('name')
        if issueuser and issueuser.getFullname():
            fromname = issueuser.getFullname()
        elif cmfuser and cmfuser.getProperty('fullname'):
            fromname = cmfuser.getProperty('fullname')
        elif self.has_cookie(ckey):
            fromname = self.get_cookie(ckey)
        else:
            fromname = ''

        ckey = self.getCookiekey('email')
        if issueuser and issueuser.getEmail():
            email = issueuser.getEmail()
        elif cmfuser and cmfuser.getProperty('email'):
            email = cmfuser.getProperty('email')
        elif self.has_cookie(ckey):
            email = self.get_cookie(ckey)
        else:
            email = ''

        saved_display_format = self.getSavedTextFormat()
        if saved_display_format:
            display_format = saved_display_format
        else:
            display_format = self.getDefaultDisplayFormat()


        try:
            note = self._createNote(comment, fromname=fromname, email=email,
                                      acl_adder=acl_adder,
                                      public=public, display_format=display_format,
                                      threadID=threadID)
        except ValueError, msg:
            if REQUEST is not None:
                return "Error: %s" % str(msg)
            else:
                raise

        if REQUEST is not None:
            redirect_url = self.absolute_url()
            request.RESPONSE.redirect(redirect_url)
        else:
            return note


    def _createNote(self, comment, fromname=None, email=None, acl_adder=None,
                   public=False, display_format='', threadID='',
                   REQUEST=None):

        # the comment can not be blank
        if not comment:
            raise IssueNoteError("Note comment can not be empty")

        if threadID:
            try:
                thread = getattr(self, threadID)
            except AttributeError:
                raise ValueError("thread does not exist")


        # test if the comment doesn't already exist
        for note in self.findNotes(comment=comment,
                                    fromname=fromname, email=email,
                                    acl_adder=acl_adder,
                                    threadID=threadID):
            # already created
            # perhaps user doubleclick the submit button
            return note

        randomid_length = self.randomid_length
        if randomid_length > 3:
            randomid_length = 3
        genid = self.generateID(randomid_length,
                                prefix=self.issueprefix + 'note',
                                meta_type=ISSUENOTE_METATYPE,
                                use_stored_counter=False)

        from IssueTrackerProduct.Note import IssueNote
        # create a note inside this issue
        note = IssueNote(genid, title, comment, fromname, email,
                         display_format=display_format,
                         acl_adder=acl_adder, threadID=threadID
                         )
        self._setObject(genid, note)
        note = self._getOb(genid)
        note.index_object()

        return note

    def findNotes(self, comment=None, fromname=None, email=None,
                  acl_adder=None, threadID=None):

        for note in self.getNotes():
            if comment is not None:
                if note.getComment() != comment:
                    continue
            if fromname is not None:
                if note.fromname != fromname:
                    continue
            if email is not None:
                if note.email != email:
                    continue
            if threadID is not None:
                if note.threadID != threadID:
                    continue
            yield note



zpts = ({'f':'zpt/ShowIssue', 'optimize':OPTIMIZE and 'xhtml'},
        'zpt/OptionButtons',

        'zpt/tell_a_friend',
        'zpt/form_followup',
        'zpt/quick_form_followup',
        'zpt/subscription',
        #'zpt/manager_options',
        #'zpt/anonymous_options',

        'zpt/form_delete',
        'zpt/followup_preview',
        )


addTemplates2Class(IssueTracker, zpts, extension='zpt')

InitializeClass(IssueTrackerIssue)

#----------------------------------------------------------------------------

class IssueTrackerDraftIssue(IssueTrackerIssue):
    """ These are used for the 'Save as draft' feature.
    It's like the regular Issue objects except that it
    doesn't get cataloged. """

    __implements__ = (IWriteLock,)

    meta_type = ISSUE_DRAFT_METATYPE
    icon = '%s/issuedraft.gif'%ICON_LOCATION

    security=ClassSecurityInfo()


    manage_options = (
        {'label':'Contents', 'action':'manage_main'},
        {'label':'Properties', 'action':'manage_draftissue_properties'}
        )


    def __init__(self, id, title=None, status=None,
                 issuetype=None, urgency=None, sections=None,
                 fromname=None, email=None, url2issue=None,
                 confidential=None, hide_me=None,
                 due_date=None,
                 description=None, display_format=None,
                 acl_adder=None, assignee_identifier=None,
                 is_autosave=False,
                 Tempfolder_fileattachments=None):
        """ init an Issue object """
        self.id = str(id)
        self.title = unicodify(title)
        self.modifydate = DateTime()
        self.status = status
        self.type = issuetype
        self.urgency = urgency
        self.sections = sections
        self.fromname = unicodify(fromname)
        if isinstance(email, basestring):
            email = asciify(email, 'ignore')
        self.email = email
        self.url2issue = url2issue
        self.confidential = confidential
        self.hide_me = hide_me
        self.due_date = due_date
        self.description = unicodify(description)
        self.display_format = display_format
        self.acl_adder = acl_adder
        self.is_autosave = not not is_autosave
        self.Tempfolder_fileattachments = Tempfolder_fileattachments

        self.assignee_identifier = assignee_identifier

    # legacy support
    is_autosave = False

    def index_object(self, *args, **kws):
        """A common method to allow Findables to index themselves."""
        pass

    def unindex_object(self):
        """A common method to allow Findables to unindex themselves."""
        pass

    def manage_afterAdd(self, REQUEST, RESPONSE):
        """ the base class defines this to prerender the description, something we
        don't want to do. """
        pass

    def getIssueDate(self):
        """ does not apply to drafts, so use modify date instead """
        return self.getModifyDate()

    def isAutosave(self):
        return self.is_autosave

    def shortDescription(self, maxlength=55, html=True):
        """ return a simplified description where the title is shown
        and then as much of the description as possible. """
        title = self.getTitle()
        if not title.strip():
            if html:
                title = "<i>(No subject)</i>"
            else:
                title = "(No subject)"
        desc = self.getDescriptionPure()

        shortened = self.lengthLimit(title, maxlength, "|...|")
        if shortened.endswith('|...|'):
            # the title was shortened
            shortened = shortened[:-len('|...|')]
            if html:
                return "<b>%s</b>..."%shortened
            else:
                return shortened+'...'
        else:
            # i.e. title==shortened
            # put some of the description ontop
            if len(shortened) + len(desc) > maxlength:
                desc = self.lengthLimit(desc, maxlength-len(title))

            if html:
                return "<b>%s</b>, %s"%(shortened, desc)
            else:
                return "%s, %s"%(shortened, desc)


    def hasThreads(self):
        """ return true if there are issuethreads within """
        return False

    def ListThreads(self):
        """ Return the followup objects. The threads. """
        return []

    def manage_beforeDelete(self, REQUEST=None, RESPONSE=None):
        """ uncatalog yourself """
        pass

    def getAssignments(self):
        """ return the issue assignment objects sorted """
        return []

    security.declareProtected('View', 'index_html')
    def index_html(self, REQUEST=None):
        """ does not apply """
        return "Drafts do not have a view part "

    def ModifyIssue(self, title=None,
                    description=None,
                    status=None,
                    type=None,
                    urgency=None,
                    sections=None,
                    fromname=None,
                    email=None,
                    url2issue=None,
                    confidential=None,
                    hide_me=None,
                    due_date=None,
                    display_format=None,
                    acl_adder=None,
                    assignee_identifier=None,
                    is_autosave=False,
                    Tempfolder_fileattachments=None,
                    REQUEST=None):
        """ Since drafts cannot have threads, we can't use the
        default ModifyIssue() which creates thread objects. """

        if title is not None:
            self.title = unicodify(title)

        if description is not None:
            self.description = unicodify(description)

        if status is not None:
            self.status = status

        if type is not None:
            self.type = type

        if urgency is not None:
            self.urgency = urgency

        if sections is not None:
            if not isinstance(sections, list):
                if isinstance(sections, tuple):
                    sections = list(sections)
                else:
                    sections = [sections]
            self.sections = sections

        if fromname is not None:
            self.fromname = unicodify(fromname)

        if email is not None:
            self.email = email

        if url2issue is not None:
            self.url2issue = url2issue

        if confidential is not None:
            self.confidential = confidential

        if hide_me is not None:
            self.hide_me = hide_me

        if due_date is not None:
            if self.parseDueDate(due_date):
                self.due_date = self.parseDueDate(due_date)

        if display_format is not None and display_format in self.display_formats:
            self.display_format = display_format

        if acl_adder is not None:
            self.acl_adder = acl_adder

        if assignee_identifier is not None:
            self.assignee_identifier = assignee_identifier

        self.is_autosave = not not is_autosave

        if Tempfolder_fileattachments is not None:
            self.Tempfolder_fileattachments = Tempfolder_fileattachments

        self.modifydate = DateTime()

    def isAutosave(self):
        """ return if this was saved as an autosave or a plain draft """
        return self.is_autosave

    def get__dict__keys(self):
        """ return the names of the keys we might have """
        return ('title', 'description', 'status', 'type', 'urgency',
                'sections', 'fromname', 'email', 'url2issue',
                'confidential', 'hide_me', 'display_format',
                'acl_adder', 'assignee_identifier', 'is_autosave',
                'due_date',
                'Tempfolder_fileattachments')

    def get__dict__nicely(self):
        """ same as get__dict__keys() but we wrap it nicely """
        ok = []
        for key in self.get__dict__keys():
            if self.__dict__.get(key, None) is not None:
                ok.append({'key':key,
                           'value':self.__dict__.get(key)})
        return ok

    def populateREQUEST(self, request):
        """ put all of this information in a request object (dict like) """
        for key in self.get__dict__keys():
            if self.__dict__.get(key):
                request.set(key, self.__dict__.get(key))


    #
    # External editor
    #

    #security.declareProtected('Use External Editor', 'manage_FTPget')
    security.declareProtected('View', 'manage_FTPget')
    def manage_FTPget(self, REQUEST, RESPONSE):
        """ get source for FTP download for ExternalEditor """
        self.REQUEST.RESPONSE.setHeader('Content-Type','text/plain')
        out = "[Subject]\n%s\n"%self.title
        out += "[Description]\n%s\n\n"%self.description
        issueuser = self.getIssueUser()
        if not issueuser:
            out += "[Name] %s\n"%self.fromname
            out += "[Email] %s\n"%self.email
            fmt = self.display_format
            fmt = fmt.replace('plaintext',"Plain as it's written")
            fmt = fmt.replace('structuredtext', "StructuredText")
            out += "[Display format] %s\n"%fmt
        out += "\n"
        sections = self.sections
        if sections is None:
            sections = []
        out += "[Sections]\n%s\n\n"%("\n".join(sections))
        out += "[Type] %s\n"%self.type
        out += "[Urgency] %s\n"%self.urgency
        out += "[URL] %s\n"%self.url2issue
        #out += "[Assign to]\n%s\n\n"%
        return out

    def get_size(self):
        """ Used for FTP and ZMI """
        return len(self.manage_FTPget())


    #security.declareProtected('Use External Editor', 'PUT')
    security.declareProtected('View', 'PUT')
    def PUT(self, REQUEST, RESPONSE):
        """ handle the HTTP PUT requests for ExternalEditor """
        self.dav__init(REQUEST, RESPONSE)
        self.dav__simpleifhandler(REQUEST, RESPONSE, refresh=1)

        if not REQUEST.get('BODY'):
            if transaction is None:
                get_transaction.abort()
            else:
                transaction.get().commit()
            RESPONSE.setStatus(405)
        else:
            body = REQUEST.get('BODY')
            info = None
            try:
                if body:
                    info = self._parseExternalEditBody(body)
            except:
                LOG(self.__class__.__name__, ERROR, "failed in _parseExternalEditBody",
                    error=sys.exc_info())
            if info is None:
                get_transaction.abort()
                RESPONSE.setStatus(405)
            else:
                apply(self.ModifyIssue, (), info)
                RESPONSE.setStatus(204)
            return RESPONSE

    def _parseExternalEditBody(self, body):
        """ return a dict of all the info we could find in this body """
        d = {}

        labels = {'Subject':'title', 'Description':'description',
                  'Name':'fromname', 'Email':'email',
                  'Display format':'display_format',
                  'Sections':'sections', 'Type':'type', 'Urgency':'urgency',
                  'URL':'url2issue'}
        body += "\n["
        for key in labels.keys():
            regex = re.compile('^\[%s\]\s*(.*?)[\[$]'%key, re.I|re.MULTILINE|re.DOTALL)
            found = regex.findall(body)
            if found:
                if found[0]:
                    value = found[0].strip()
                else:
                    value = ''
                tidied = self._tidyFoundValue(labels.get(key), value)
                if tidied is not None:
                    d[labels.get(key)] = tidied

        return d

    def _tidyFoundValue(self, key, value):
        """ massage the value based on what the key is """
        if key == 'display_format':
            if value.find("Plain as it's written") > -1:
                return 'plaintext'
            elif value.find("StructuredText") > -1:
                return 'structuredtext'
            else:
                # regular expression
                if re.compile('structured', re.I).findall(value):
                    return 'structuredtext'
                else:
                    return 'plaintext'
        elif key == 'sections':
            sections = value
            if not isinstance(sections, list):
                sections = sections.replace(',','\n')
                sections = sections.split('\n')
                sections = Utils.uniqify(sections)
                while '' in sections:
                    sections.remove('')
                if not self.CanAddNewSections():
                    # remove all that we don't recognize
                    options = [Utils.ss(x) for x in self.sections_options]
                    sections = [x for x in sections if Utils.ss(x) in options]
            return sections
        elif key == 'urgency':
            for urgencyoption in self.urgencies:
                # makes sure the value is of correct case
                if Utils.ss(value) == Utils.ss(urgencyoption):
                    return urgencyoption

            return None # if the above loop didn't work the value is unrecongized
        elif key == 'type':
            for typeoption in self.types:
                # makes sure the value is of correct case
                if Utils.ss(value) == Utils.ss(typeoption):
                    return typeoption
            return None # see above on urgencies

        # all else, nothing to complain or nag about
        return value


dtmls = ({'f':'dtml/draftissue_properties', 'n':'manage_draftissue_properties'},
         )
addTemplates2Class(IssueTrackerDraftIssue, dtmls, "dtml")
InitializeClass(IssueTrackerDraftIssue)


#----------------------------------------------------------------------------

from Notification import IssueTrackerNotification
from Thread import IssueTrackerIssueThread, IssueTrackerDraftIssueThread
from Assignment import IssueTrackerIssueAssignment
