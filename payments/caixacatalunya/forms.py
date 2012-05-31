# -*- coding: utf-8 -*-

from django import forms
from django.utils.translation import ugettext_lazy as _
from ..forms import PaymentForm

class CaixaCatalunyaXMLForm(PaymentForm):
    '''
    Payment form, suitable for Django templates.
    
    When displaying the form remeber to use *action* and *method*.
    '''
    Ds_Merchant_Pan = forms.CharField(max_length=16, label=_(u'Número de tarjeta:'))
    Ds_Merchant_Expirydate_month = forms.CharField(max_length=2, label=_(u'Mes:'))
    Ds_Merchant_Expirydate_year = forms.CharField(max_length=2, label=_(u'Año:'))
    Ds_Merchant_CVV2 = forms.CharField(max_length=3, label=_(u'CVV2:'))
