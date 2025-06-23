from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Savings)
admin.site.register(Interest)
admin.site.register(Loanable)
admin.site.register(Investment)