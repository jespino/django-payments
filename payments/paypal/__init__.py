# -*- coding: utf-8 -*-
import urlparse

from django.shortcuts import get_object_or_404
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.utils.http import urlquote
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import translation

from .. import BasicProvider
from ..models import Payment
import requests
import urllib
import urllib2

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
    _action = "https://www.paypal.com/cgi-bin/webscr"
    _url_name = ''

    def __init__(self, bussiness, cart_name, currency_iso_code, pdt_key, url_name=None, domain=None, **kwargs):
        self._bussiness = bussiness
        self._currency_iso_code = currency_iso_code
        self._cart_name = cart_name
        self._pdt_key = pdt_key

        self._url_name = url_name or self._url_name

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
        url = urlparse.urlunparse((domain.scheme, domain.netloc, reverse(self._url_name, kwargs={'id': payment.id}), None, None, None))

        data = {
            "cmd": "_cart",
            "upload": "1",
            "business": self._bussiness,
            "shopping_url": self._domain,
            "currency_code": self._currency_iso_code,
            "return": url,
            "notify_url" : urlc,
            "rm": "1",
            "email": payment.get_customer_detail('email'),
            "first_name": payment.get_customer_detail('first_name'),
            "last_name": payment.get_customer_detail('last_name'),
            "address1": payment.get_customer_detail('address'),
            "city": payment.get_customer_detail('city'),
            "state": payment.get_customer_detail('state'),
            "zip": payment.get_customer_detail('postcode'),
            "charset": "utf-8",
            "lc": translation.get_language().upper(),
            "item_name": self._cart_name,
            "no_shipping": 1,
            "no_note": 1,
            "custom": payment.id,
        }


        total_discount = 0
        total_amount = 0
        payment_items = payment.items.all()
        counter = 1
        for key in range(len(payment_items)):
            if int(payment_items[key].unit_price) >= 0:
                if payment_items[key].is_shipping:
                    data["item_name_%d" % (counter)] = payment_items[key].name
                    data["amount_%d" % (counter)] = "%.2f" % payment_items[key].unit_price
                    data["quantity_%d" % (counter)] = int(payment_items[key].quantity)
                    data["image_url_%d" % (counter)] = ""
                else:
                    data["item_name_%d" % (counter)] = payment_items[key].name
                    data["amount_%d" % (counter)] = "%.2f" % payment_items[key].unit_price
                    data["quantity_%d" % (counter)] = int(payment_items[key].quantity)
                    data["image_url_%d" % (counter)] = ""
                    total_amount += payment_items[key].unit_price * int(payment_items[key].quantity)
                counter += 1
            else:
                total_discount += -payment_items[key].unit_price

        if payment.total > 0:
            data["discount_amount_cart"] = "%.2f" % (total_discount,)
        else:
            data["discount_amount_cart"] = "%.2f" % (total_amount,)

        return data
           # {% if bypass_uuid %}
           # "bypass_uuid": "{{ bypass_uuid }}"
           # {% endif %}

    def process_data(self, request, variant):
        """
            View called from paypal for validating a payment
        """

        #print ("Paypal calling finish transaction: payment_uuid %s" % (payment_uuid))
        print ("Paypal post request: %s" % (str(request.POST)))

        payment_id = request.POST.get('custom', 0)
        payment = get_object_or_404(Payment, pk=payment_id)
        payment_status = request.POST.get('payment_status', '')
        pending_reason = request.POST.get('pending_reason', '')

        #Para confirmar:
        notification_status = urllib2.urlopen(self._action, "cmd=_notify-validate&%s" % request.body).read()
        print ("Paypal notification_status: %s" %(notification_status))
        print ("Paypal payment_status: %s" %(payment_status))
        #print ("Paypal payment.sale_order.status: %s" %(payment.sale_order.status))

        if notification_status == 'VERIFIED':
            if (payment_status == 'Completed' or \
                    (payment_status == 'Pending' and pending_reason in ['verify', 'echeck']) or \
                    (payment_status == 'Pending' and pending_reason=='multi_currency')):

                print ("Paypal paypal_finish_transaction: ok")

                print ("Paypal Updating payment in django")
                paypal_txn_id = request.POST.get('txn_id', '')
                payment.transaction_id = paypal_txn_id

                payment.change_status("confirmed")
                print payment.status
                print payment.id

            elif payment_status == 'Denied':
                print ("Paypal paypal_finish_transaction: error")

                payment.change_status("rejected")
                print payment.status
                print payment.id

            return HttpResponse('Ok', mimetype="text/plain")

        return HttpResponseBadRequest()
