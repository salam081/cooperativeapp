from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(LoanRequest)
admin.site.register(LoanRepayback)
admin.site.register(LoanType)
# admin.site.register(ConsumableItem)
admin.site.register(BankName)
admin.site.register(BankCode)
admin.site.register(LoanSettings)