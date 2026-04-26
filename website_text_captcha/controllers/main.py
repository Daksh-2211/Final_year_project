import json
import random
import string
import logging

from captcha.image import ImageCaptcha

from odoo import http, _
from odoo.http import request
from odoo.addons.website.controllers.form import WebsiteForm
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
import base64
from operator import itemgetter
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.osv.expression import AND
from odoo.tools import email_normalize, escape_psql

_logger = logging.getLogger(__name__)


class CaptchaController(http.Controller):

    @http.route('/captcha/image', type='http', auth="public", website=True, sitemap=False)
    def captcha_image(self, **kwargs):
        image_generator = ImageCaptcha(width=200, height=60, font_sizes=(35, 40, 45))
        captcha_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

        request.session['captcha_code'] = captcha_code
        _logger.info(f"CAPTCHA: Generated New Code -> {captcha_code}")

        data = image_generator.generate(captcha_code)
        return request.make_response(
            data.read(),
            headers=[
                ('Content-Type', 'image/png'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Expires', '0'),
            ]
        )


class WebsiteFormCaptcha(WebsiteForm):

    @http.route(
        '/website/form/<string:model_name>',
        type='http',
        auth="public",
        methods=['POST'],
        website=True,
        csrf=False
    )
    def website_form(self, model_name, **kwargs):

        protected_models = ['crm.lead', 'helpdesk.ticket']

        if model_name in protected_models:
            user_input_raw = kwargs.get('captcha_input', '')
            user_input_clean = (user_input_raw or '').strip().upper()

            session_code_raw = request.session.get('captcha_code', '')
            session_code_clean = (session_code_raw or '').strip().upper()

            if not user_input_clean or not session_code_clean or user_input_clean != session_code_clean:
                _logger.warning(f"CAPTCHA FAILED - codes do not match (Input='{user_input_clean}' vs Session='{session_code_clean}')")
                return request.make_json_response(
                    {'error': 'Security Check Failed: The captcha code is incorrect. Please try again.'},
                    status=400
                )

            _logger.info("CAPTCHA PASSED - proceeding")
            request.session.pop('captcha_code', None)  # Only clear on success
            if 'captcha_input' in kwargs:
                del kwargs['captcha_input']

        try:
            return super(WebsiteFormCaptcha, self).website_form(model_name, **kwargs)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            _logger.error(f"Form submission failed after CAPTCHA pass: {str(e)}\nFull traceback:\n{error_details}")
            return request.make_json_response(
                {'error': f'Form error: {str(e)}. Please check required fields or configuration.'},
                status=400
            )


class WebsiteHrRecruitmentCustom(WebsiteHrRecruitment):

    @http.route('/website_hr_recruitment/check_recent_application', type='json', auth="public", website=True)
    def check_recent_application(self, field, value, job_id):
        def refused_applicants_condition(applicant):
            return not applicant.active \
                and applicant.job_id.id == int(job_id) \
                and applicant.create_date >= (datetime.now() - relativedelta(months=6))

        field_domain = {
            'name': [('partner_name', '=ilike', escape_psql(value))],
            'email': [('email_normalized', '=', email_normalize(value))],
            'phone': [('partner_phone', '=', value)],
            'linkedin': [('linkedin_profile', '=ilike', escape_psql(value))],
        }.get(field, [])

        applications_by_status = http.request.env['hr.applicant'].sudo().search(AND([
            field_domain,
            [
                ('job_id.website_id', 'in', [http.request.website.id, False]),
                '|',
                ('application_status', '=', 'ongoing'),
                '&',
                ('application_status', '=', 'refused'),
                ('active', '=', False),
            ]
        ]), order='create_date DESC').grouped('application_status')

        refused_applicants = applications_by_status.get('refused', http.request.env['hr.applicant'])
        if any(applicant for applicant in refused_applicants if refused_applicants_condition(applicant)):
            return {
                'message': _(
                    'Našli sme predchádzajúcu uzavretú žiadosť v našom systéme za posledných 6 mesiacov.'
                    ' Prosím, zvážte pred opätovným podaním, aby sa predišlo duplicite.'
                )
            }

        if 'ongoing' not in applications_by_status:
            return {'message': None}

        ongoing_application = applications_by_status.get('ongoing')[0]
        if ongoing_application.job_id.id == int(job_id):
            recruiter_contact = "" if not ongoing_application.user_id else _(
                ' V prípade problémov kontaktujte %(contact_infos)s',
                contact_infos=", ".join(
                    [value for value in itemgetter('name', 'email', 'phone')(ongoing_application.user_id) if value]
                ))
            return {
                'message': _(
                    'Pre %(value)s už existuje žiadosť.'
                    ' Duplikáty môžu byť zamietnuté. %(recruiter_contact)s',
                    value=value,
                    recruiter_contact=recruiter_contact
                )
            }

        return {
            'message': _(
                'Našli sme nedávnu žiadosť s podobným menom, e-mailom alebo telefónnym číslom.'
                ' Môžete pokračovať, ak to nie je chyba.'
            )
        }

    def insert_attachment(self, model, id_record, files):
        if model.sudo().model == 'hr.applicant':
            candidate_id = request.env['hr.applicant'].browse(id_record).candidate_id
            if candidate_id:
                attachment_value = []
                for file in files:
                    if file_data := file.read():
                        attachment_value.append({
                            'name': file.filename,
                            'datas': base64.b64encode(file_data),
                            'res_model': 'hr.candidate',
                            'res_id': candidate_id.id,
                        })
                        file.stream.seek(0)
                if attachment_value:
                    request.env['ir.attachment'].sudo().create(attachment_value)

        return super(WebsiteHrRecruitment, self).insert_attachment(model, id_record, files)