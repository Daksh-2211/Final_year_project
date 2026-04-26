# -*- coding: utf-8 -*-
import werkzeug
import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.utils import ensure_db
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.exceptions import UserError
from odoo.addons.odoo_marketplace.controllers.main import AuthSignupHome, website_marketplace_dashboard
from odoo.addons.website.controllers.main import Website

_logger = logging.getLogger(__name__)


def _get_seller_dashboard_url():
    """
    Redirecting the seller to the portal dashboard.
    """
    try:
        menu_id = request.env['ir.model.data'].sudo().check_object_reference(
            'odoo_marketplace', 'wk_seller_dashboard'
        )[1]
        return "/web#menu_id=" + str(menu_id)
    except Exception as e:
        return '/my/account'


class AuthSignupHomePortalFix(AuthSignupHome):
    @http.route(website=True, auth="public", sitemap=False)
    def web_login(self, *args, **kw):
        """
        Override: fix the seller dashboard redirect for portal users.
        """
        ensure_db()
        response = Website.web_login(self, *args, **kw)
        if request.params.get('login_success'):
            current_user = request.env['res.users'].browse(request.uid)
            if (
                    not current_user.has_group('base.group_user')
                    and current_user.has_group('odoo_marketplace.marketplace_draft_seller_group')
                    and current_user.partner_id.seller
            ):
                redirect = _get_seller_dashboard_url()
                return werkzeug.utils.redirect(redirect)
        return response

    @http.route('/seller/signup', type='http', auth="public", website=True)
    def seller_signup_form(self, *args, **kw):
        """
        Override: fix the post-signup redirect for portal sellers.
        """
        if not request.website.enable_marketplace:
            return request.render('http_routing.404')

        qcontext = self.get_auth_signup_qcontext()
        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if kw.get("name", False):
            if 'error' not in qcontext and request.httprequest.method == 'POST':
                try:
                    self.do_signup(qcontext)
                    self.web_login(*args, **kw)

                    # Request approval automatically since portal sellers can't access the backend button
                    user_login = qcontext.get('login')
                    if user_login:
                        new_user = request.env['res.users'].sudo().search([('login', '=', user_login)], limit=1)
                        if new_user and new_user.partner_id.seller and new_user.partner_id.state not in ['pending',
                                                                                                         'approved']:
                            new_user.partner_id.sudo().set_to_pending()

                    return request.redirect(_get_seller_dashboard_url())
                except UserError as e:
                    qcontext['error'] = str(e)
                except (SignupError, AssertionError) as e:
                    if request.env["res.users"].sudo().search(
                            [("login", "=", qcontext.get("login"))]
                    ):
                        qcontext["error"] = _(
                            "Another user is already registered using this email address."
                        )
                    else:
                        qcontext['error'] = _("Could not create a new account.")
            if kw.get("signup_from_seller_page", False) == "true":
                qcontext.pop("error", None)
                qcontext.update({"set_seller": True, 'hide_top_menu': True})

        return request.render('odoo_marketplace.mp_seller_signup', qcontext)


class WebsiteMarketplaceDashboardPortalFix(website_marketplace_dashboard):
    """
    Override: Portal users converting to a seller also trigger the approval workflow.
    """

    @http.route('/my/marketplace/seller', type='http', auth="public", website=True)
    def submit_as_seller(self, **post):
        response = super(WebsiteMarketplaceDashboardPortalFix, self).submit_as_seller(**post)
        if request.env.user and request.env.user.partner_id.seller and request.env.user.partner_id.state not in [
            'pending', 'approved']:
            request.env.user.partner_id.sudo().set_to_pending()
        return response
