# -*- coding: utf-8 -*-
import urlparse
import hashlib
import random

from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.utils.http import urlquote
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.views.generic.simple import direct_to_template
from django.template import Template, Context
import requests
import urllib
import re

from .. import BasicProvider
from ..models import Payment
from .constants import *
from ..signals import *

ORDER_CODE_OFFSET = 10000000000

class CaixaCatalunyaBaseProvider(BasicProvider):
    '''
    Caixa Catalunya Virtual POS payment provider

    merchant_code:
        merchant code, assigned by Caixa Catalunya
    secret_code:
        secret code, assigned by Caixa Catalunya
    merchant_titular:
        Titular to show to the user
    merchant_name:
        Name to show to the user
    terminal_number:
        terminal used to pay
    payment_url:
        url used to start payment
    currency_code:
        terminal used to pay
    transaction_type:
        transaction type
    lang:
        language selected
    '''
    _lang = '0'
    _transaction_type = '0'
    _currency_code = '978'
    _redirect_url = ''

    def __init__(self, merchant_code, secret_code, merchant_titular, merchant_name, terminal_number, transaction_type=None, lang=None, domain=None, domain_protocol="http", currency_code=None, redirect_url=None, **kwargs):
        self._merchant_code = merchant_code
        self._secret_code = secret_code
        self._merchant_titular = merchant_titular
        self._merchant_name = merchant_name
        self._terminal_number = terminal_number
        self._redirect_url = redirect_url

        self._lang = lang or self._lang
        self._transaction_type = transaction_type or self._transaction_type

        self._currency_code = currency_code or self._currency_code

        self._domain = domain or urlparse.urlunparse((
                    domain_protocol,
                    Site.objects.get_current().domain,
                    '/',
                    None,
                    None,
                    None))

        domain = urlparse.urlparse(self._domain)
        path = reverse('process_payment', args=[kwargs.get('variant')])
        self._urlc = urlparse.urlunparse((domain.scheme, domain.netloc, path, None, None, None))

        return super(CaixaCatalunyaBaseProvider, self).__init__(**kwargs)

    def generate_message_digest(self, data):
        raise NotImplementedError

    def generate_response_digest(self, data):
        raise NotImplementedError

    def get_hidden_fields(self, payment):
        get_label = lambda x: x.name if x.quantity == 1 else u'%s × %d' % (x.name, x.quantity)
        items = map(get_label, payment.items.all())

        total = Decimal(0)
        for elem in payment.items.filter(is_shipping=False):
            total += elem.quantity * elem.unit_price
        if total < 0:
            total = 0
        for elem in payment.items.filter(is_shipping=True):
            total += elem.quantity * elem.unit_price

        data = {
                'Ds_Merchant_Amount': str(int(float(total)*100)),
                'Ds_Merchant_Currency': self._currency_code,
                'Ds_Merchant_Order': "%04d" % (ORDER_CODE_OFFSET+payment.id),
                'Ds_Merchant_MerchantURL': self._urlc,
                'Ds_Merchant_ProductDescription': ', '.join(items),
                'Ds_Merchant_Titular': self._merchant_titular,
                'Ds_Merchant_MerchantName': self._merchant_name,
                'Ds_Merchant_Terminal': self._terminal_number,
                'Ds_Merchant_MerchantCode': self._merchant_code,
                'Ds_Merchant_TransactionType': self._transaction_type,
        }
        return data

class CaixaCatalunyaHTMLProvider(CaixaCatalunyaBaseProvider):
    _action = 'https://sis.sermepa.es/sis/realizarPago'

    def get_hidden_fields(self, payment):
        data = super(CaixaCatalunyaHTMLProvider, self).get_hidden_fields(payment)

        data['Ds_Merchant_UrlOK'] = self._urlc
        data['Ds_Merchant_UrlKO'] = self._urlc
        data['Ds_Merchant_MerchantSignature'] = self.generate_message_digest(data)

        return data

    def process_data(self, request, variant):
        data = request.GET

        payment_id = int(data['Ds_Order'])-ORDER_CODE_OFFSET
        payment = get_object_or_404(Payment, pk=payment_id)

        if self.generate_response_digest(data) == data['Ds_Signature'] and int(data['Ds_Response'])<=99:
            status = "confirmed"
            error_message = u''
        else:
            status = "rejected"
            error_message = ERRORS.get(str(int(data['Ds_Response'])),data['Ds_Response'])

        payment.change_status(status)
        return HttpResponseRedirect(reverse(self._redirect_url, args=[payment.id]))

    def generate_message_digest(self, data):
        return hashlib.sha1(
                data['Ds_Merchant_Amount'] + \
                data['Ds_Merchant_Order'] + \
                data['Ds_Merchant_MerchantCode'] + \
                data['Ds_Merchant_Currency'] + \
                data['Ds_Merchant_TransactionType'] + \
                data['Ds_Merchant_MerchantURL'] + \
                self._secret_code).hexdigest().upper()

    def generate_response_digest(self, data):
        return hashlib.sha1(
                data['Ds_Amount'] + \
                data['Ds_Order'] + \
                data['Ds_MerchantCode'] + \
                data['Ds_Currency'] + \
                data['Ds_Response'] + \
                self._secret_code).hexdigest().upper()

class CaixaCatalunyaXMLProvider(CaixaCatalunyaBaseProvider):
    _version = 1.999008881
    _payment_url = 'https://sis.sermepa.es/sis/operaciones'

    def process_data(self, request, variant):
        if request.method == "POST":
            data = request.POST.copy()

            data['Ds_Merchant_Expirydate'] = data['Ds_Merchant_Expirydate_year']+data['Ds_Merchant_Expirydate_month']
            data['Ds_Merchant_MerchantSignature'] = self.generate_message_digest(data)

            xml_template = Template("""
            <DATOSENTRADA>
            <DS_VERSION>{{ version|safe }}</DS_VERSION>
            <DS_MERCHANT_CURRENCY>{{ Ds_Merchant_Currency }}</DS_MERCHANT_CURRENCY>
            <DS_MERCHANT_TRANSACTIONTYPE>{{ Ds_Merchant_TransactionType }}</DS_MERCHANT_TRANSACTIONTYPE>
            <DS_MERCHANT_AMOUNT>{{ Ds_Merchant_Amount }}</DS_MERCHANT_AMOUNT>
            <DS_MERCHANT_MERCHANTCODE>{{ Ds_Merchant_MerchantCode }}</DS_MERCHANT_MERCHANTCODE>
            <DS_MERCHANT_MERCHANTURL>{{ Ds_Merchant_MerchantUrl }}</DS_MERCHANT_MERCHANTURL>
            <DS_MERCHANT_TERMINAL>{{ Ds_Merchant_Terminal }}</DS_MERCHANT_TERMINAL>
            <DS_MERCHANT_ORDER>{{ Ds_Merchant_Order }}</DS_MERCHANT_ORDER>
            <DS_MERCHANT_PAN>{{ Ds_Merchant_Pan }}</DS_MERCHANT_PAN>
            <DS_MERCHANT_EXPIRYDATE>{{ Ds_Merchant_Expirydate }}</DS_MERCHANT_EXPIRYDATE>
            <DS_MERCHANT_CVV2>{{ Ds_Merchant_CVV2 }}</DS_MERCHANT_CVV2>
            <DS_MERCHANT_MERCHANTSIGNATURE>{{ Ds_Merchant_MerchantSignature }}</DS_MERCHANT_MERCHANTSIGNATURE>
            </DATOSENTRADA>
            """)

            payment_id = int(data['Ds_Merchant_Order'])-ORDER_CODE_OFFSET
            payment = get_object_or_404(Payment, pk=payment_id)

            context = Context()
            context['version'] = self._version
            for key, value in data.iteritems():
                context[key] = value
            data = xml_template.render(context)
            response = requests.post(self._payment_url, {'entrada': data})
            if response.text.startswith('<!-- ReciboOK -->'):
                status = "confirmed"
                error_message = ''
            else:
                status = "rejected"
                match = re.search('<!--SIS(\d\d\d\d):-->', response.text)
                sys_error = match.group(1)
                error_message_code = SYS_ERRORS[sys_error]
                error_message = MESSAGES[error_message_code]

            payment.change_status(status)
            payment_finished.send(sender=type(payment), instance=payment)

            return HttpResponseRedirect(reverse(self._redirect_url, args=[payment.id]))

    def generate_message_digest(self, data):
        return hashlib.sha1(
                data['Ds_Merchant_Amount'] + \
                data['Ds_Merchant_Order'] + \
                data['Ds_Merchant_MerchantCode'] + \
                data['Ds_Merchant_Currency'] + \
                data['Ds_Merchant_Pan'] + \
                data['Ds_Merchant_CVV2'] + \
                data['Ds_Merchant_TransactionType'] + \
                self._secret_code).hexdigest().upper()

    def get_form(self, payment):
        '''
        Converts *payment* into a form suitable for Django templates.
        '''
        from .forms import CaixaCatalunyaXMLForm
        return CaixaCatalunyaXMLForm(self.get_hidden_fields(payment), self._action, self._method)
