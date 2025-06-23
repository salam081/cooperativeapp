from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(State)
admin.site.register(Address)
admin.site.register(User)
admin.site.register(Member)
admin.site.register(UserGroup)
admin.site.register(Gender)
admin.site.register(Religion)