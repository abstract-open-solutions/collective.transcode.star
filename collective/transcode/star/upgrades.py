import logging

from Products.CMFCore.utils import getToolByName

import plone.api


product = 'collective.transcode.star'
default_profile = 'profile-%s:default' % product
logger = logging.getLogger('[%s-UPGRADE]' % product.upper())


def upgrade(upgrade_product, version):
    """ Decorator for updating the QuickInstaller of a upgrade
    see http://www.uwosh.edu/ploneprojects/
    docs/how-tos/how-to-use-generic-setup-upgrade-steps
    """
    def wrap_func(fn):
        def wrap_func_args(context, *args):
            p = getToolByName(
                context, 'portal_quickinstaller').get(upgrade_product)
            setattr(p, 'installedversion', version)
            return fn(context, *args)
        return wrap_func_args
    return wrap_func


@upgrade(product, '1.0.2')
def upgrade_to_1002(context):
    version = '1.0.2'
    logger.info("Upgrading to %s version" % version)
    update_css_to_1002(context)


def update_css_to_1002(context):
    logger.info("adding stylesheets")
    to_add = (
        '++resource++collective.transcode.css',
    )
    csstool = plone.api.portal.get_tool('portal_css')
    for res in to_add:
        csstool.registerResource(res)
        logger.info("added %s" % res)
    csstool.cookResources()

