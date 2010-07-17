"""Event subscribers"""
import logging

from zope.component import adapter
from zope.component import getUtility
from zope.component import getSiteManager
from zope.interface.interfaces import IInterface
from zope.component.interfaces import ObjectEvent

from collective.transcode.interfaces import ITranscodeTool

log = logging.getLogger('collective.transcode')

def is_transcode_installed(object):
    sm = getSiteManager(context=object)
    return sm.queryUtility(ITranscodeTool, default=False)

@adapter(IContentish, IObjectCreatedEvent)
def addFile(obj, event):
    editFile(obj, event)

@adapter(IContentish, IObjectModifiedEvent)
def editFile(obj, event):
    if is_transcode_installed(obj) is False:
        return
    if not obj.UID():
        return
    try:
        registry = getUtility(IRegistry)
        types = registry['collective.transcode.interfaces.ITranscodeSettings.portal_types']
        newTypes = [t.split(':')[0] for t in types]
        if unicode(obj.portal_type) not in newTypes:
            return
        fieldNames = [str(t.split(':')[1]) for t in types if ('%s:' % unicode(obj.portal_type)) in t]
        tt = getUtility(ITranscodeTool)
        tt.add(obj, fieldNames)
    except Exception, e:
        log.error("Could not transcode resource %s\n Exception: %s" % (obj.absolute_url(), e))

