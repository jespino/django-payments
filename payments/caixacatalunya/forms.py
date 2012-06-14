# -*- coding: utf-8 -*-

from django import forms
from django.utils.translation import ugettext_lazy as _
from ..forms import PaymentForm
from datetime import date

MONTH_CHOICES = [
    ('01', _('January')),
    ('02', _('February')),
    ('03', _('March')),
    ('04', _('April')),
    ('05', _('May')),
    ('06', _('June')),
    ('07', _('July')),
    ('08', _('August')),
    ('09', _('September')),
    ('10', _('October')),
    ('11', _('November')),
    ('12', _('December')),
]

YEAR_CHOICES = [ (x % 100,str(x)) for x in range(date.today().year,date.today().year+50) ]

class CaixaCatalunyaXMLForm(PaymentForm):
    '''
    Payment form, suitable for Django templates.
    
    When displaying the form remeber to use *action* and *method*.
    '''
    Ds_Merchant_Pan = forms.CharField(max_length=16, label=_(u'Número de tarjeta:'))
    Ds_Merchant_Expirydate_month = forms.ChoiceField(label=_(u'Mes:'), choices=MONTH_CHOICES)
    Ds_Merchant_Expirydate_year = forms.ChoiceField(label=_(u'Año:'), choices=YEAR_CHOICES)
    Ds_Merchant_CVV2 = forms.CharField(max_length=3, label=_(u'CVV2:'))
