from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.db.models import Prefetch
from django.core.paginator import Paginator
import pandas as pd
from django.db import transaction
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum, F, Q
from collections import defaultdict
from datetime import datetime,date
from decimal import Decimal
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.files.base import ContentFile
import os
from .models import *
from loan.models import *

from django.contrib.admin.views.decorators import staff_member_required


def add_consumables_items(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        price = request.POST.get('price')
        Item.objects.create(title=title,price=price,available=True)
        messages.success(request,'Item Added Successfully')
        return redirect('consumable_items')
    
def delete_item(request,id):
    itemObj = get_object_or_404(Item, id=id)
    itemObj.delete()
    messages.success(request, 'Consumable item Deleted successfully')
    return redirect('consumable_items')

def consumable_items(request):
    consumables = Item.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        price = request.POST.get('price')
        item_id = request.POST.get('item_id')
        action = request.POST.get('action')  # either 'toggle' or 'edit'
        
        if item_id:
            item = get_object_or_404(Item, id=item_id)

            if action == 'toggle':
                item.available = not item.available
                item.save()
                messages.success(request, 'Consumable item availability updated successfully')
                return redirect('consumable_items')

            elif action == 'edit':
                item.title = title
                item.price = price
                item.save()
                messages.success(request, 'Consumable item updated successfully')
                return redirect('consumable_items')
            
            
        else:
            item = Item.objects.create(title=title,price=price,available=True)
            item.save()
            messages.success(request, 'Consumable item Created successfully')
            return redirect('consumable_items')
            # messages.error(request, 'Item ID not provided.')
            # return redirect('consumable_items')
    
    context = {'consumables': consumables}
    return render(request, "consumables/consumable_items.html", context)


def consumable_requests_list(request):
    if request.method == 'POST':
        if 'remove_item_id' in request.POST:
            detail_id = request.POST.get('remove_item_id')
            detail = get_object_or_404(ConsumableRequestDetail, id=detail_id)
            if detail.request.status == 'Pending':
                detail.delete()
                messages.success(request, "Item removed successfully.")
            else:
                messages.error(request, "Cannot remove item from an approved request.")
            return redirect('consumable_requests_list')

        elif 'reduce_quantity_id' in request.POST:
            detail_id = request.POST.get('reduce_quantity_id')
            new_quantity = request.POST.get('new_quantity')
            detail = get_object_or_404(ConsumableRequestDetail, id=detail_id)

            if detail.request.status != 'Pending':
                messages.error(request, "Cannot reduce quantity on an approved request.")
            elif new_quantity.isdigit() and 0 < int(new_quantity) < detail.quantity:
                detail.quantity = int(new_quantity)
                detail.save()
                messages.success(request, "Quantity reduced successfully.")
            elif int(new_quantity) == detail.quantity:
                messages.info(request, "Quantity is unchanged.")
            else:
                messages.error(request, "Invalid quantity. Must be lower than current value and greater than 0.")
            return redirect('consumable_requests_list')

    search_query = request.GET.get('q', '').strip()

    # Show all if searching
    if search_query:
        requests = ConsumableRequest.objects.filter(
            Q(user__first_name__icontains=search_query) | 
            Q(user__last_name__icontains=search_query) | 
            Q(user__username__icontains=search_query) | 
            Q(status__iexact=search_query) | 
            Q(details__item__title__icontains=search_query)
        ).distinct()
    else:
        # Only non-approved requests when not searching
        # requests = ConsumableRequest.objects.exclude(status='Approved')
        requests = ConsumableRequest.objects.exclude(status__in=['Approved', 'Paid'])


    requests = requests.prefetch_related(Prefetch('details__item')).order_by('-date_created')

    paginator = Paginator(requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'requests':requests

    }
    return render(request, 'consumables/request_list.html', context)



@staff_member_required
def admin_edit_consumable_request(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id, status='Pending')
    items = Item.objects.filter(available=True)
    details = ConsumableRequestDetail.objects.filter(request=consumable_request)

    # Only allow the admin to change the loan term
    if request.method == 'POST':
        loan_term_months = request.POST.get('loan_term_months')

        if not loan_term_months or not loan_term_months.isdigit() or int(loan_term_months) <= 0:
            messages.error(request, "Please provide a valid loan term.")
            return render(request, 'consumables/admin_edit_request.html', {
                'items': items,
                'details': details,
                'request_obj': consumable_request
            })

        try:
            with transaction.atomic():
                # Update the loan term for the existing request
                for detail in details:
                    detail.loan_term_months = int(loan_term_months)
                    detail.save()

            messages.success(request, "Loan term updated successfully.")
            return redirect('consumable_requests_list')

        except Exception as e:
            # messages.error(request, f"An error occurred: {e}")
            return render(request, 'consumables/admin_edit_request.html', {
                'items': items,
                'details': details,
                'request_obj': consumable_request
            })

    return render(request, 'consumables/admin_edit_request.html', {
        'items': items,
        'details': details,
        'request_obj': consumable_request
    })


def approve_consumable_request(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)

    if consumable_request.status != 'Pending':
        messages.warning(request, 'This request is already processed.')
    else:
        consumable_request.status = 'Approved'
        consumable_request.save()

        # Carry forward previous balance
        previous = ConsumableRequest.objects.filter(
            user=consumable_request.user, 
            status='Approved'
        ).exclude(id=consumable_request.id).order_by('-date_created').first()

        previous_balance = 0
        if previous:
            previous_total = previous.calculate_total_price()
            previous_paid = previous.total_paid()
            previous_balance = previous_total - previous_paid

        new_total = consumable_request.calculate_total_price()
        final_total = new_total + previous_balance

        PaybackConsumable.objects.create(
            consumable_request=consumable_request,
            amount_paid=0,
            repayment_date=date.today(), 
            balance_remaining=final_total
        )

        messages.success(request, 'The request has been approved and previous balance carried forward.')
    return redirect('consumable_requests_list')


def decline_consumable_request(request, request_id):
    consumable_request = get_object_or_404(ConsumableRequest, id=request_id)
    
    if consumable_request.status != 'Pending':
        messages.warning(request, 'This request is already processed.')
    else:
        consumable_request.status = 'Declined'
        consumable_request.save()
        messages.success(request, 'The request has been declined.')
    
    return redirect('consumable_requests_list')


def add_single_consumable_payment(request):
    requests = []
    selected_user = None

    ippis = request.GET.get("ippis") or request.POST.get("ippis")
    if ippis:
        try:
            member = Member.objects.filter(ippis=int(ippis)).first()
            if member and member.member:
                selected_user = member.member
                requests = ConsumableRequest.objects.filter(
                    user=selected_user
                ).exclude(status='Paid')  # Only show unpaid or partially paid requests
        except Exception as e:
            messages.error(request, f"Error fetching member: {e}")

    if request.method == "POST":
        amount_paid = request.POST.get("amount_paid")
        month = request.POST.get("month")
        request_id = request.POST.get("consumable_request")

        if not ippis or not amount_paid or not month or not request_id:
            messages.error(request, "All fields are required.")
            return redirect(request.path + f"?ippis={ippis}")

        try:
            amount_paid = Decimal(amount_paid)
            month = parse_date(month)
            request_id = int(request_id)
            if not month:
                raise ValueError("Invalid date format.")
        except Exception as e:
            messages.error(request, f"Invalid input: {e}")
            return redirect(request.path + f"?ippis={ippis}")

        consumable_request = ConsumableRequest.objects.filter(id=request_id, user=selected_user).first()
        if not consumable_request:
            messages.error(request, "Selected consumable request not found.")
            return redirect(request.path + f"?ippis={ippis}")

        total_paid = PaybackConsumable.objects.filter(consumable_request=consumable_request).aggregate(
            total=Sum("amount_paid")
        )["total"] or Decimal('0')

        remaining_balance = consumable_request.calculate_total_price() - total_paid

        if amount_paid > remaining_balance:
            messages.error(request, "Payment exceeds remaining balance.")
            return redirect(request.path + f"?ippis={ippis}")

        already_paid = PaybackConsumable.objects.filter(
            consumable_request=consumable_request,
            repayment_date__year=month.year,
            repayment_date__month=month.month
        ).exists()

        if already_paid:
            messages.warning(request, f"Payment already exists for {month.strftime('%B %Y')}.")
            return redirect(request.path + f"?ippis={ippis}")

        with transaction.atomic():
            PaybackConsumable.objects.create(
                consumable_request=consumable_request,
                amount_paid=amount_paid,
                repayment_date=month
            )

            new_total_paid = PaybackConsumable.objects.filter(consumable_request=consumable_request).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')

            if new_total_paid >= consumable_request.calculate_total_price():
                consumable_request.status = 'Paid'
                consumable_request.save()

        messages.success(request, f"Payment of ₦{amount_paid} recorded for {selected_user.first_name} ({ippis}).")
        return redirect(request.path + f"?ippis={ippis}")

    return render(request, "consumables/add_single_payment.html", { "requests": requests, "selected_user": selected_user,})


def upload_consumable_payment(request):
    available_requests = ConsumableRequest.objects.filter(status="Approved").select_related("user")
    grouped_by_month = defaultdict(list)

    for req in available_requests:
        if req.balance() > 0:
            month_key = req.date_created.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
            grouped_by_month[month_key].append(req)

    grouped_list = sorted(grouped_by_month.items())

    if request.method == "POST":
        selected_request_month_str = request.POST.get("selected_month")
        file = request.FILES.get("excel_file")

        if not selected_request_month_str or not file:
            messages.error(request, "Both month and file are required.")
            return redirect("upload_consumable_payment")

        try:
            selected_request_month = datetime.strptime(selected_request_month_str, "%Y-%m").date().replace(day=1)
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect("upload_consumable_payment")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f"Error reading Excel file: {e}")
            return redirect("upload_consumable_payment")

        required_cols = {"IPPIS", "Amount Paid", "Repayment Date"}
        if not required_cols.issubset(df.columns):
            messages.error(request, "Excel must contain 'IPPIS', 'Amount Paid', and 'Repayment Date' columns.")
            return redirect("upload_consumable_payment")

        # Filter only requests created in the selected request month
        matching_requests = [
            req for req in grouped_by_month.get(selected_request_month, [])
        ]
        # Build IPPIS-to-request mapping from the selected request month
        ippis_to_request = {}
        for req in matching_requests:
            user = req.user
            if user and hasattr(user, "member") and user.member and user.member.ippis:
                ippis_to_request[str(user.member.ippis)] = req


        uploaded = 0
        skipped = []

        for _, row in df.iterrows():
            ippis = str(row["IPPIS"]).strip()
            amount = row["Amount Paid"]
            repayment_date_raw = row["Repayment Date"]

            try:
               repayment_month = pd.to_datetime(row["Repayment Date"]).date().replace(day=1)

            except Exception:
                skipped.append(ippis)
                continue

            request_obj = ippis_to_request.get(ippis)
            if not request_obj:
                skipped.append(ippis)
                continue

            # Prevent duplicate repayment for the same request & month
            if PaybackConsumable.objects.filter(
                    consumable_request=request_obj,
                    repayment_date=repayment_month
                ).exists():
                skipped.append(ippis)
                continue

            PaybackConsumable.objects.create(
                consumable_request=request_obj,
                amount_paid=Decimal(amount),
                repayment_date=repayment_month
            )
            uploaded += 1

        messages.success(request, f"{uploaded} payment(s) uploaded successfully.")
        if skipped:
            messages.warning(request, f"Skipped IPPIS: {', '.join(skipped)}")

        return redirect("upload_consumable_payment")

    context = {"grouped_list": grouped_list}
    return render(request, "consumables/upload_consumable_payment.html", context)


def consumable_requests_by_month(request):
    details = ConsumableRequestDetail.objects.select_related('request', 'item', 'request__user')

    grouped_by_month = defaultdict(list)
    for detail in details:
        month = detail.request.date_created.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        grouped_by_month[month].append(detail)

    # Convert dict to list of tuples for template: [(month, [details]), ...]
    grouped_list = sorted(grouped_by_month.items())
    context = {'grouped_list': grouped_list,}
    return render(request, 'consumables/monthly_summary.html', context)


def consumable_details(request, month):
    try:
        month_date = datetime.strptime(month, "%Y-%m")
    except ValueError:
        return render(request, "consumables/grouped_details.html", {"error": "Invalid month format."})

    # Filter for this particular month's requests
    monthly_qs = ConsumableRequestDetail.objects.filter(
        date_created__year=month_date.year,
        date_created__month=month_date.month
    )
    approved_total = monthly_qs.filter(
        request__status='Approved'
    ).aggregate(total=Sum(F('quantity') * F('item_price')))['total'] or 0

    pending_total = monthly_qs.filter(
        request__status='Pending'
    ).aggregate(total=Sum(F('quantity') * F('item_price')))['total'] or 0

    paid_total = monthly_qs.filter(
        request__status='Paid'
    ).aggregate(total=Sum(F('quantity') * F('item_price')))['total'] or 0

    details = monthly_qs.select_related('item', 'request__user')

    user_data = defaultdict(list)
    for detail in details:
        user_data[detail.request.user].append(detail)

    grouped_data = []
    for user, items in user_data.items():
        total = sum(d.total_price for d in items)

        consumable_request = ConsumableRequest.objects.filter(
            user=user, 
            status__in=['Approved', 'Paid']
        ).first()

        if consumable_request:
            amount_paid = PaybackConsumable.objects.filter(
                consumable_request=consumable_request
            ).aggregate(total=models.Sum('amount_paid'))['total'] or 0

            last_payment = PaybackConsumable.objects.filter(
                consumable_request=consumable_request
            ).order_by('-repayment_date').first()
            current_payment = last_payment.amount_paid if last_payment else 0
        else:
            amount_paid = 0
            current_payment = 0

        grouped_data.append({ 
            "user": user, 
            "items": items, 
            "total": total, 
            "amount_paid": amount_paid,
            "current_payment": current_payment,
        })

    context = {
        "month": month_date,
        "grouped_data": grouped_data,
        'approved_total': approved_total,
        'pending_total': pending_total,
        'paid_total': paid_total,
    }
    return render(request, "consumables/grouped_details.html", context)


def consumable_repayments_list(request):
    repayments_qs = PaybackConsumable.objects.select_related(
        "consumable_request", "consumable_request__user"
    ).order_by("-repayment_date")

    # Filters
    selected_month = request.GET.get("month")
    user_search = request.GET.get("user_search", "").strip()

    filters = Q()

    if selected_month:
        parsed_date = datetime.strptime(selected_month, "%Y-%m")
        filters &= Q(
            repayment_date__year=parsed_date.year,
            repayment_date__month=parsed_date.month
        )

    if user_search:
        filters &= (
            Q(consumable_request__user__first_name__icontains=user_search) |
            Q(consumable_request__user__last_name__icontains=user_search) |
            Q(consumable_request__user__member__ippis__icontains=user_search)
        )

    repayments_qs = repayments_qs.filter(filters)

    # Pagination
    paginator = Paginator(repayments_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Summary
    total_paid = repayments_qs.aggregate(total=Sum("amount_paid"))["total"] or 0
    total_remaining = repayments_qs.aggregate(total=Sum("balance_remaining"))["total"] or 0

    # Distinct months for filtering
    months = PaybackConsumable.objects.annotate(
        month=TruncMonth("repayment_date")
    ).values_list("month", flat=True).distinct().order_by("-month")

    context = {
        "page_obj": page_obj,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
        "months": months,
        "selected_month": selected_month,
        "user_search": user_search,
    }
    return render(request, "consumables/consumable_repayments_list.html", context)







