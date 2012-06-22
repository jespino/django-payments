# -*- coding: utf-8 -*-
import urlparse

from django.shortcuts import get_object_or_404
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.utils.http import urlquote
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.generic.simple import direct_to_template
from django.utils import translation

from .. import BasicProvider
from ..models import Payment
from ..signals import *

import requests
import urllib
import urllib2

class TransferProvider(BasicProvider):
    '''
    transfer payment provider
    '''
    _url_name = ''

    def __init__(self, url_name=None, domain=None, **kwargs):
        self._url_name = url_name or self._url_name

        self._domain = domain or urlparse.urlunparse((
                    'http',
                    Site.objects.get_current().domain,
                    '/',
                    None,
                    None,
                    None))
        return super(TransferProvider, self).__init__(**kwargs)

    def get_hidden_fields(self, payment):
        data = { 'payment_id': payment.id }
        return data

    def process_data(self, request, variant):
        payment_id = request.POST.get('payment_id', 0)
        payment = get_object_or_404(Payment, pk=payment_id)
        payment.change_status("waiting")

        payment_finished.send(sender=type(payment), instance=payment)
        return direct_to_template(request, 'payments/transfer/return.html', {'payment': payment})
