from django.db import models
from accounts.models import *


class Savings(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    month = models.DateField(db_index=True)
    month_saving = models.DecimalField(max_digits=10, decimal_places=2)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # total_amonth_save = models.DecimalField(max_digits=12, decimal_places=2,)
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ("member", "month")  # Prevents duplicates for the same month

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.member.update_total_savings()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.member.update_total_savings()

    def __str__(self):
        return f"{self.member} - {self.month.strftime('%B %Y')}: ₦{self.month_saving}"


class Interest(models.Model):
    member = models.ForeignKey('accounts.Member', on_delete=models.CASCADE)
    month = models.DateField(db_index=True)  
    amount_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=400.00)
    date_deducted = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ("member", "month")  # Prevent duplicate deductions

    def __str__(self):
        return f"{self.member} - {self.amount_deducted} for {self.month.strftime('%B %Y')}"


class Loanable(models.Model):
    member = models.ForeignKey('accounts.Member', on_delete=models.CASCADE)
    month = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    
    
    def __str__(self):
        return f"{self.member} - {self.amount} -  {self.month.strftime('%B %Y')}"



class Investment(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    month = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.member} - {self.amount} - {self.month.strftime('%B %Y')}"


