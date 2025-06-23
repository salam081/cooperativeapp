from django.db import models
from django.utils import timezone
from accounts.models import *
from main.models import *
# Create your models here.


class LoanSettings(models.Model):
    allow_loan_requests = models.BooleanField(default=True)
    allow_consumable_requests = models.BooleanField(default=True)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    
    # def __str__(self):
    #     return f"{self.allow_loan_requests} ({self.allow_consumable_requests})"
     

class BankName(models.Model):
     name = models.CharField(max_length=100)
     def __str__(self):
        return self.name
     
class BankCode(models.Model):
    bank_name = models.ForeignKey(BankName, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('bank_name', 'name')  

    def __str__(self):
        return f"{self.name} ({self.bank_name.name})"
     

class LoanType(models.Model):
    name = models.CharField(max_length=100) 
    description = models.TextField(blank=True, null=True) 
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) 
    max_loan_term_months = models.PositiveIntegerField(null=True, blank=True) 
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

def today_date():
    return timezone.now().date()

class LoanRequest(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="loan_requests")
    loan_type = models.ForeignKey(LoanType, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    loan_term_months = models.PositiveIntegerField()
    application_date = models.DateField(default=today_date)
    approval_date = models.DateField(null=True, blank=True) 
    status = models.CharField(max_length=20,choices=[ ("pending", "Pending"),("approved", "Approved"),("rejected", "Rejected"),  ("paid", "paid"),("paid", "paid") ], default="pending",)
    rejection_reason = models.TextField(blank=True, null=True)
    file_one = models.ImageField(upload_to='file_one', blank=True, null=True)
    bank_name = models.ForeignKey(BankName,on_delete=models.CASCADE)
    bank_code = models.ForeignKey(BankCode,on_delete=models.CASCADE)
    account_number  = models.CharField(max_length=100)
    guarantor_name  = models.CharField(max_length=100)
    guarantor_ippis  = models.CharField(max_length=100)
    guarantor_phone  = models.CharField(max_length=100)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    
    @property
    def monthly_payment(self):
        if self.approved_amount and self.loan_term_months > 0:
            # Calculate the monthly payment based on the approved amount and loan term
            # Still assuming no interest for simplicity here
            total_payment = self.approved_amount
            return total_payment / self.loan_term_months
        return None  # Or handle the case where approved_amount or loan_term_months is not set

    def __str__(self):
        return f"Loan Request for {self.member} - Amount: {self.amount} - Approved Amount: {self.approved_amount if self.approved_amount else 'Pending'}"


class LoanRepayback(models.Model):
    loan_request = models.ForeignKey(LoanRequest, on_delete=models.CASCADE, related_name="repaybacks")
    repayment_date = models.DateField()  
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)  
    balance_remaining = models.DecimalField(max_digits=10, decimal_places=2) 
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    
    def __str__(self):
        return f"Repayment of {self.amount_paid} for Loan ID {self.loan_request.member} on {self.repayment_date}"
    

