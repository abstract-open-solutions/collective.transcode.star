try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from base64 import b64encode, b64decode
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager

from zope.interface import implements
from zope.interface import Interface
from zope.component import getUtility

from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName

from plone.memoize.view import memoize_contextless
from plone.memoize.view import memoize

from collective.transcode.star.crypto import decrypt
from collective.transcode.star.interfaces import ICallbackView
from collective.transcode.star.interfaces import ITranscodeTool
from collective.transcode.star.interfaces import ITranscoded
from collective.transcode.star.utility import get_settings
from collective.transcode.star import _

import logging

try:
    from collective.transcode.burnstation.interfaces import IBurnTool
    BURNSTATION_SUPPORT = True
except ImportError:
    BURNSTATION_SUPPORT = False

log = logging.getLogger('collective.transcode')


class EmbedView(BrowserView):

    """
        Embedded video vew
    """

    @property
    def helpers(self):
        return self.context.restrictedTraverse('@@transcode-helpers')

    def jpeg(self):
        try:
            url = self.helpers.download_links()['jpeg']
            print url
            return url
        except:
            return False

    def profiles(self):
        try:
            return self.helpers.profiles
        except:
            return

    def canDownload(self):
        return self.helpers.showDownload()

    def __call__(self):
        """Override X-Frame-Options.

        cfr.: https://github.com/plone/plone.protect#clickjacking-protection
        http://sgr.casaccia.enea.it/issuetracker/issue-tracker/551
        """
        self.request.response.setHeader(
            'X-Frame-Options',
            'ALLOW-FROM http://transcoder.webtv.enea.it'
        )   
        return super(EmbedView, self).__call__()


class CallbackView(BrowserView):
    """
        Handle callbacks and errbacks from transcode daemon
    """
    implements(ICallbackView)
    def callback_xmlrpc(self, result):
        """
           Handle callbacks
        """
        tt = getUtility(ITranscodeTool)
        secret = tt.secret()
        try:
            result = eval(decrypt(b64decode(result['key']), secret), {"__builtins__":None},{})
            assert result.__class__ is dict
        except Exception as e:
            log.error("Unauthorized callback %s" % result)
            return

        if result['profile'] == 'iso' and BURNSTATION_SUPPORT:
            bt = getUtility(IBurnTool)
            if result['path']:
                bt.callback(result)
            else:
                bt.errback(result)
        else:
            if result['path']:
                tt.callback(result)
            else:
                tt.errback(result)


class ServeDaemonView(BrowserView):
    """
        Handle callbacks from transcode daemon
    """
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        try:
            tt = getUtility(ITranscodeTool)
            key = self.request['key']
            input = decrypt(b64decode(key), tt.secret())
            (uid, fieldName, profile) = eval(input, {"__builtins__":None},{})
            obj = self.context.uid_catalog(UID=uid)[0].getObject()
            if not fieldName:
                fieldName = obj.getPrimaryField().getName()
            field = obj.getField(fieldName)
            if tt[uid][fieldName][profile]['status']!='pending':
                log.error('status not pending')
                raise
            pm = getToolByName(self.context, 'portal_membership')
            newSecurityManager(self.request,pm.getMemberById(self.context.getOwner().getId()))
            if field.getFilename(obj).__class__ is unicode:
                # Monkey patch the getFilename to go around plone.app.blob unicode filename bug
                def getFilenameAsString(obj):
                    return field.oldGetFilename(obj).encode(obj.getCharset(),'ignore')
                field.oldGetFilename = field.getFilename
                field.getFilename = getFilenameAsString
                dl = field.download(obj)
                field.getFilename = field.oldGetFilename
                del field.oldGetFilename
                return dl
            else:
                return field.download(obj)
        except Exception as e:
            log.error('Unauthorized file request: %s' % e)
            return


class IHelpers(Interface):

    def settings():
        """ return global settings
        """

    def tool():
        """ return transcode tool
        """

    def profiles():
        """ return transcode profiles for context
        """

    def showDownload():
        """ return true if user can download video
        """

    def download_links(video_only=1):
        """ return download links for context
        """

    def fieldname():
        """ return field name
        """

    def display_size():
        """ return video display size
        """

    def get_progress(profile_name):
        """ return trancoding progress for given profile
        """

    def is_transcoded():
        """ return ttrue if the video has been transcoded.
        """


# TODO: make this configurable
PROFILES_TITLE = {
    'mp4-low': _(u"MP4 Low Resolution"),
    'mp4-high': _(u"MP4 High Resolution"),
    'webm-low': _(u"WEBM Low Resolution"),
    'webm-high': _(u"WEBM High Resolution"),
}

IMG_PROFILES = ['jpeg', ]


class Helpers(BrowserView):

    implements(IHelpers)

    @property
    @memoize_contextless
    def settings(self):
        return get_settings()

    @property
    @memoize_contextless
    def tool(self):
        return getUtility(ITranscodeTool)

    @property
    @memoize
    def info(self):
        uid = self.context.UID()
        return self.tool[uid]

    def get_progress(self, profile_name):
        return self.tool.getProgress(self.profiles[profile_name]['jobId'])

    @property
    def fieldname(self):
        # what if we have more fnames???
        return self.info.keys()[0]

    @property
    @memoize
    def profiles(self):
        try:
            # what if we have more fnames???
            return self.info[self.fieldname]
        except:
            return {}

    def showDownload(self):
        return self.settings.showDownload

    @memoize
    def download_links(self, video_only=True):
        # let's keep them ordered
        links = OrderedDict()
        # add original link
        if self.fieldname:
            title = _(u'Original')
            title += ' (%s)' % self.display_size()
            links['original'] = {
                'title': title,
                'url': '%s/at_download/%s' % (self.context.absolute_url(),
                                              self.fieldname),
            }
        for name, data in self.profiles.iteritems():
            if video_only and name in IMG_PROFILES:
                continue
            if not data.get('path'):
                # something went wrong with transcoding of this profile
                msg = 'transcode profile "%s" error: %s' % (name,
                                                            data['status'])
                log.info(msg)
                continue
            if data['address']:
                links[name] = {
                    'title': PROFILES_TITLE.get(name, name),
                    'url': data['address'] + '/' + data['path'],
                }
        return links

    def display_size(self):
        size = self.context[self.fieldname].get_size()
        size_kb = size / 1024
        size_mb = size_kb / 1024
        display_size_mb = '{0:n} MB'.format(size_mb) if size_mb > 0 else ''
        display_size_kb = '{0:n} kB'.format(size_kb) if size_kb > 0 else ''
        display_size_bytes = '{0:n} bytes'.format(size)
        display_size = display_size_mb or display_size_kb or display_size_bytes
        return display_size

    def is_transcoded(self):
        return ITranscoded.providedBy(self.context)


class RenderPlayer(BrowserView):

    @property
    def helpers(self):
        return self.context.restrictedTraverse('@@transcode-helpers')

    def update(self):
        try:
            self.fieldname = self.helpers.fieldname
            self.profiles = self.helpers.profiles
        except KeyError:
            pass

    def display_size(self):
        return self.helpers.display_size()

    def show_subs(self):
        return self.helpers.settings.subtitles
