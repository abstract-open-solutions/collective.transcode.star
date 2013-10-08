from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.layout.viewlets.common import ViewletBase


class TranscodeViewlet(ViewletBase):
    render = ViewPageTemplateFile('viewlet.pt')


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
