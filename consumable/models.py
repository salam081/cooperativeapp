from django.db.models import Sum
from django.db import models
from accounts.models import *
from django.db.models import Sum
from django.utils import timezone


class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class ConsumableRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
        ('Paid', 'Paid'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"Request #{self.id} by {self.user.username}"

    def calculate_total_price(self):
        return sum(detail.total_price for detail in self.details.all())

    def total_paid(self):
        return self.repayments.aggregate(total=Sum('amount_paid'))['total'] or 0

    def balance(self):
        return self.calculate_total_price() - self.total_paid()

class ConsumableRequestDetail(models.Model):
    request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="details")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    loan_term_months = models.PositiveIntegerField()
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True) 
    date_created = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.quantity * self.item_price
    
    
    
    def __str__(self):
        return f"{self.request} {self.quantity} x {self.item.title} (Req #{self.request.id})"
    

class PaybackConsumable(models.Model):
    consumable_request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="repayments")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateField()
    balance_remaining = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            self.update_balance()

    def update_balance(self):
        total_price = self.consumable_request.calculate_total_price()

        # Total paid including this new payment
        total_paid = self.consumable_request.repayments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0

        balance = total_price - total_paid
        self.balance_remaining = balance

        # Save updated balance to this record
        PaybackConsumable.objects.filter(pk=self.pk).update(balance_remaining=balance)

        # Update request status if paid
        if balance <= 0:
            self.consumable_request.status = 'Paid'
            self.consumable_request.save()

    def __str__(self):
        return f"₦{self.amount_paid} for Req#{self.consumable_request.id} on {self.repayment_date}"


# class PaybackConsumable(models.Model):
#     consumable_request = models.ForeignKey( ConsumableRequest, on_delete=models.CASCADE, related_name="repayments")
#     amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
#     repayment_date = models.DateField()
#     balance_remaining = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

#     def save(self, *args, **kwargs):
#         # Call super() first so that we get an ID if it's a new object
#         super().save(*args, **kwargs)

#         # After saving, update the balance
#         self.update_balance()

#     def update_balance(self):
#         total_price = self.consumable_request.calculate_total_price()
#         total_paid = self.consumable_request.repayments.aggregate(
#             total=Sum('amount_paid')
#         )['total'] or 0

#         balance = total_price - total_paid
#         # Optional: mark as "Paid" if fully paid
#         if balance <= 0:
#             self.consumable_request.status = 'Paid'
#             self.consumable_request.save()

#     def __str__(self):
#         return f"₦{self.amount_paid} for Req#{self.consumable_request.id} on {self.repayment_date}"
