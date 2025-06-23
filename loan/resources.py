from import_export import resources
from .models import *


class LoanRepaybackResources(resources.ModelResource):
    class meta:
        model = LoanRepayback

