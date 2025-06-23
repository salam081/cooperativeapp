from django.db import models
from django.conf import settings
from decimal import Decimal
from accounts.models import *

class FinancialSummary(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="financial_summaries")
    total_savings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_interest = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_loanable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_investment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        timestamp = self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        if self.user:
            return f"Summary for {self.user.username} at {timestamp} - Grand Total: {self.grand_total}"
        return f"Summary at {timestamp} (No User) - Grand Total: {self.grand_total}"

    class Meta:
        verbose_name = "Financial Summary"
        verbose_name_plural = "Financial Summaries"
        ordering = ['-created_at']
