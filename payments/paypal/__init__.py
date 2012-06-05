# -*- coding: utf-8 -*-
import urlparse

from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.utils.http import urlquote
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import translation

from .. import BasicProvider
from ..models import Payment
import requests
import urllib

class PaypalProvider(BasicProvider):
    '''
    paypal.com payment provider

    username:
        seller ID, assigned by dotpay
    password:
        return URL, user will be bounced to this address after payment is
        processed
    signature:
        PIN
    action:
        default payment channel (consult dotpay.pl reference guide)
    lang:
        UI language
    lock:
        whether to disable channels other than the default selected above
    '''
    _action = "https://www.sandbox.paypal.com/cgi-bin/webscr"
    _url = ''

    def __init__(self, bussiness, cart_name, currency_iso_code, pdt_key, url=None, domain=None, **kwargs):
        self._bussiness = bussiness
        self._currency_iso_code = currency_iso_code
        self._cart_name = cart_name
        self._pdt_key = pdt_key

        self._url = url or self._url

        self._domain = domain or urlparse.urlunparse((
                    'http',
                    Site.objects.get_current().domain,
                    '/',
                    None,
                    None,
                    None))
        return super(PaypalProvider, self).__init__(**kwargs)

    def get_hidden_fields(self, payment):
        get_label = lambda x: x.name if x.quantity == 1 else u'%s × %d' % (x.name, x.quantity)
        items = map(get_label, payment.items.all())

        domain = urlparse.urlparse(self._domain)
        path = reverse('process_payment', args=[self._variant])
        urlc = urlparse.urlunparse((domain.scheme, domain.netloc, path, None, None, None))

        data = {
            "cmd": "_cart",
            "upload": "1",
            "business": self._bussiness,
            "shopping_url": self._domain,
            "currency_code": self._currency_iso_code,
            "return": urlc,
            "notify_url" : urlc,
            "rm": "1",
            "item_number_1": payment.id,
            "item_name_1": self._cart_name,
            "amount_1": payment.total,
            "quantity_1": "1",
            "image_url_1": "",
            "email": "",
            #"first_name": payment.customer_details.all()[0].first_name,
            #"last_name": payment.customer_details.last_name,
            #"address1": payment.customer_details.billing_address,
            #"city": payment.customer_details.billing_city,
            "first_name": "",
            "last_name": "",
            "address1": "",
            "city": "",
            "state": "",
            #"zip": payment.customer_details.billing_postcode,
            "zip": "",
            "day_phone_a": "",
            "day_phone_b": "",
            "night_phone_b": "",
            "charset": "utf-8",
            "lc": translation.get_language().upper(),
        }
        return data
           # {% if bypass_uuid %}
           # "bypass_uuid": "{{ bypass_uuid }}"
           # {% endif %}

    def process_data(self, request, variant):
        from django.core.mail import mail_admins
        mail_admins('Payment', unicode(request.POST) + '\n' + unicode(request.GET))
        failed = HttpResponseForbidden("FAILED")
        if request.method != "POST":
            return failed


        data = request.POST.copy()

        data['USER'] = self._username
        data['PWD'] = self._password
        data['SIGNATURE'] = self._signature
        data['METHOD'] = 'SetExpressCheckout'
        data['VERSION'] = self._paypal_version
        data['BUYERUSER'] = 'tonin_1338359374_per@kaleidos.net'

        response = requests.post(self._payment_url, data)
        response = { x.split("=")[0]:x.split("=")[1] for x in urllib.unquote_plus(response.text).split("&") }
        print response

        data2 = request.POST.copy()
        data2['METHOD'] = 'GetExpressCheckoutDetails'
        data2['TOKEN'] = response['TOKEN']
        response = requests.post(self._payment_url, data2)
        response = { x.split("=")[0]:x.split("=")[1] for x in urllib.unquote_plus(response.text).split("&") }
        print response

        raise Exception("QUITOOOO TOROOOOO")

        data3 = request.POST.copy()
        data3['USER'] = self._username
        data3['PWD'] = self._password
        data3['SIGNATURE'] = self._signature
        data3['METHOD'] = 'SetExpressCheckout'
        data3['TOKEN'] = response['TOKEN']
        data3['VERSION'] = self._paypal_version


        raise Exception("QUITOOOO TOROOOOO")

        DoExpressCheckoutPayment

        return HttpResponse(response.text)

        form.save()
        return HttpResponse("OK")
