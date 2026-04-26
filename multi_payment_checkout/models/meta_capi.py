# -*- coding: utf-8 -*-
import json
import logging
import requests
import hashlib
from datetime import datetime
from odoo import models, api

_logger = logging.getLogger(__name__)


class MetaCAPI(models.AbstractModel):
    _name = 'meta.capi.service'
    _description = 'Meta Conversions API Service'

    @api.model
    def send_purchase_event(self, registration_ids):
        """
        Sends a Purchase event to Meta Conversions API for the given event registrations.
        Should be called asynchronously.
        """
        pixel_id = self.env['ir.config_parameter'].sudo().get_param('meta.pixel_id')
        access_token = self.env['ir.config_parameter'].sudo().get_param('meta.capi_token')

        if not pixel_id or not access_token:
            _logger.warning("Meta CAPI skip: Missing 'meta.pixel_id' or 'meta.capi_token' in System Parameters.")
            return False

        registrations = self.env['event.registration'].sudo().browse(registration_ids)
        if not registrations:
            return False

        events_data = []
        for reg in registrations:
            event = reg.event_id
            ticket = reg.event_ticket_id
            partner = reg.partner_id

            # Hash email if available (Meta requires SHA256 hashed user data)
            em = partner.email or reg.email or ''
            em_hash = hashlib.sha256(em.strip().lower().encode('utf-8')).hexdigest() if em else None

            ph = partner.phone or reg.phone or ''
            ph_hash = hashlib.sha256(
                ph.strip().replace('+', '').replace(' ', '').encode('utf-8')).hexdigest() if ph else None

            # Deduplication ID perfectly matching the frontend window.dataLayer push
            event_id = f"reg_{reg.id}"

            # Prepare user_data
            user_data = {}

            user_agent = self.env.context.get('user_agent')
            if user_agent:
                user_data['client_user_agent'] = user_agent

            if em_hash: user_data['em'] = em_hash
            if ph_hash: user_data['ph'] = ph_hash

            # Try to get client IP from request if available in the context
            client_ip = self.env.context.get('client_ip')
            if client_ip:
                user_data['client_ip_address'] = client_ip

            # Standard Meta Event payload
            payload = {
                "event_name": "Purchase",
                "event_time": int(datetime.now().timestamp()),
                "event_id": event_id,
                "event_source_url": f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/event/{event.id}",
                "action_source": "website",
                "user_data": user_data,
                "custom_data": {
                    "currency": event.company_id.currency_id.name or 'EUR',
                    "value": ticket.price if ticket else 0.0,
                    "content_name": event.name,
                    "content_ids": [str(event.id)],
                    "content_type": "product",
                    "registration_id": str(reg.id)
                }
            }
            events_data.append(payload)

        if not events_data:
            return False

        api_url = f"https://graph.facebook.com/v18.0/{pixel_id}/events"
        params = {
            'access_token': access_token
        }

        try:
            response = requests.post(api_url, params=params, json={
                "data": events_data,
            }, timeout=10)
            response.raise_for_status()
            _logger.info("Meta CAPI Purchase Event Sent Successfully: %s", response.json())
            return True
        except requests.exceptions.RequestException as e:
            _logger.error("Meta CAPI Purchase Event Failed: %s - Response: %s", str(e),
                          getattr(e.response, 'text', 'No Response'))
            return False
