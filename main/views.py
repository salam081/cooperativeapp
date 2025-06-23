import os
import pandas as pd
import calendar
from django.shortcuts import render, redirect,get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
from django.http import JsonResponse, HttpResponseNotAllowed
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
from datetime import timedelta
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils.dateparse import parse_date
from .models import * 


def index(request):
     return render(request, "main/index.html")

def search_member_for_savings(request):
    results = []
    search_term = request.GET.get('search_term', '').strip()
    if search_term:
        results = Member.objects.select_related('member').filter(
            Q(member__first_name__icontains=search_term) |
            Q(member__last_name__icontains=search_term) |
            Q(ippis__icontains=search_term) |
            Q(id__icontains=search_term)
        ).order_by('member__first_name', 'member__last_name')

        paginator = Paginator(results, 100)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    else:
        page_obj = []

    context = {
        'results': page_obj,
        'search_term': search_term,
    }
    return render(request, 'main/search_member.html', context)


def add_individual_member_savings(request, id):
    member = get_object_or_404(Member, id=id)
    if request.method == 'POST':
        month_str = request.POST.get('month')
        month_saving_str = request.POST.get('month_saving')

        if not month_str or not month_saving_str:
            messages.error(request, "Please provide both the month and the saving amount.")
        else:
            try:
                month = timezone.datetime.strptime(month_str, '%Y-%m-%d').date()
                month_saving = float(month_saving_str)

                if Savings.objects.filter(member=member, month=month).exists():
                    messages.warning(request, f"Savings for {member.member} for {month.strftime('%Y-%m-%d')} already exists.")
                else:
                    Savings.objects.create(member=member, month=month, month_saving=month_saving)
                    messages.success(request, f"Savings for {member.member} added successfully.")
                    return redirect('add_individual_savings', id=id)
            except ValueError:
                messages.error(request, "Invalid date format or saving amount.")

    context = {'member': member,}
    return render(request, 'main/add_individual_savings.html', context)



def upload_savings(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        selected_month = request.POST.get("month")

        # Validate month selection
        if not selected_month:
            messages.error(request, "Please select a month before uploading.")
            return redirect(request.path)

        try:
            # Parse the selected month as a date
            month_date = datetime.strptime(selected_month, "%Y-%m").date().replace(day=1)

            # Save the uploaded file temporarily
            relative_path = default_storage.save(f"upload/{excel_file.name}", ContentFile(excel_file.read()))
            absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            # Read the Excel file using pandas
            df = pd.read_excel(absolute_path, engine="openpyxl")
            # Delete the temporary file after reading
            default_storage.delete(relative_path)

            if df.empty:
                messages.error(request, "The uploaded file is empty.")
                return redirect(request.path)

            # Validate necessary columns in the Excel file
            required_columns = {"ippis", "amount"}
            if not required_columns.issubset(df.columns):
                messages.error(request, "Excel must contain: ippis, amount.")
                return redirect(request.path)

            total_added = 0
            total_updated = 0
            total_skipped = 0
            # List to hold IPPIS numbers of skipped members
            skipped_ippis = []  

            # Process each row in the Excel file
            with transaction.atomic():  # Ensuring atomicity of the operations
                for _, row in df.iterrows():
                    ippis = row.get("ippis")
                    amount = row.get("amount")

                    # Skip incomplete rows
                    if pd.isna(ippis) or pd.isna(amount):
                        total_skipped += 1
                        continue

                    try:
                        ippis = int(ippis)
                        amount = Decimal(str(amount))
                    except ValueError:
                        total_skipped += 1
                        continue

                    # Find the member by IPPIS
                    member = Member.objects.filter(ippis=ippis).first()
                    if not member:
                        total_skipped += 1
                        continue

                    # Try to get or create a savings record for the member and the month
                    savings, created = Savings.objects.get_or_create(member=member, month=month_date,
                        defaults={ "month_saving": amount,"original_amount": amount, })

                    # If the savings already exist for the month, skip it
                    if not created:
                        skipped_ippis.append(ippis)  # Add to the skipped list
                        total_skipped += 1
                    else:
                        total_added += 1

            # Construct the message for skipped IPPIS numbers
            if skipped_ippis:
                skipped_ippis_str = ', '.join(map(str, skipped_ippis))
                messages.info(request,f"Skipped IPPIS numbers: {skipped_ippis_str} - Savings already exist for these members for {month_date.strftime('%B %Y')}.")

            # Provide feedback on the result
            messages.success( request,f"Upload complete: {total_added} added, {total_updated} updated, {total_skipped} skipped." )
            return redirect(request.path)

        except Exception as e:
            # Handle any errors during file processing
            messages.error(request, f"Error processing file: {str(e)}")
            return redirect(request.path)

    return render(request, "main/upload_savings.html")



def get_upload_savings(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    savings = Savings.objects.all()

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            savings = savings.filter(month__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            savings = savings.filter(month__lte=date_to_parsed)
        except ValueError:
            pass

    months = savings.annotate(
        month_num=ExtractMonth("month"),
        year_num=ExtractYear("month")
    ).values("month_num", "year_num").distinct()

    data = [
        {"num": m["month_num"], "year": m["year_num"], "name": calendar.month_name[m["month_num"]]}
        for m in months if m["month_num"]
    ]

    # Sort by year then month (optional)
    data.sort(key=lambda x: (x["year"], x["num"]))

    # Paginator setup
    paginator = Paginator(data, 12)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "main/get_upload_savings.html", {"page_obj": page_obj,"date_from": date_from,"date_to": date_to})



def get_upload_details(request, month):
    savings_list = Savings.objects.filter(month__month=month)
    paginator = Paginator(savings_list, 100)  # Show 10 items per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request,"main/get_upload_savings_details.html",{"page_obj": page_obj})


def delete_saving(request, month):
    savings_qs = Savings.objects.filter(month__month=month)
    affected_member = set(saving.member for saving in savings_qs)
    savings_qs.delete()
    for member in affected_member:
        member.update_total_savings()

    messages.success(request, f"Deleted savings records for {calendar.month_name[month]} .")    
    return redirect("get_upload_savings")




def interest_form_view(request):
    # messages.success(request, f" deducted successfully")
    return render(request, 'main/deduct_interest_form.html')


def deduct_monthly_interest(request):
    if request.method == 'POST':
        deduction_amount_str = request.POST.get('deduction_amount')
        month_str = request.POST.get('month')  # Format: 'YYYY-MM'

        if not deduction_amount_str or not month_str:
            messages.error(request, "Please enter both the month and deduction amount.")
            return redirect('interest_form')

        try:
            year, month = map(int, month_str.split('-'))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return redirect('interest_form')

        try:
            deduction_amount = Decimal(deduction_amount_str)
            if deduction_amount <= Decimal("0.00"):
                messages.error(request, "Deduction amount must be greater than zero.")
                return redirect('interest_form')
        except DecimalException:
            messages.error(request, "Invalid deduction amount.")
            return redirect('interest_form')

        savings_this_month = Savings.objects.filter(month__year=year, month__month=month)
        count = 0

        for saving in savings_this_month:
            member = saving.member
            already_deducted = Interest.objects.filter(member=member, month=saving.month).exists()

            if not already_deducted and saving.month_saving >= deduction_amount:
                if saving.original_amount is None:
                    saving.original_amount = saving.month_saving

                saving.month_saving -= deduction_amount
                saving.save()

                Interest.objects.create(member=member, month=saving.month, amount_deducted=deduction_amount)
                count += 1

        if count:
            messages.success(request, f"₦{deduction_amount} deducted from {count} members for {calendar.month_name[month]} {year}.")
            return redirect('get_upload_interest')
        else:
            messages.info(request, f"No deductions made for {calendar.month_name[month]} {year}. Either already deducted .")
            return redirect('interest_form')

    return redirect('interest_form')

# def deduct_monthly_interest(request, year, month):
#     if request.method == 'POST':
#         deduction_amount_str = request.POST.get('deduction_amount')
#         if not deduction_amount_str:
#             messages.error(request, "Please enter the amount to deduct.")
#             return redirect('interest_form')  

#         try:
#             deduction_amount = Decimal(deduction_amount_str)
#             if deduction_amount <= Decimal("0.00"):
#                 messages.error(request, "Deduction amount must be greater than zero.")
#                 return redirect('interest_form')
#         except DecimalException:
#             messages.error(request, "Invalid deduction amount. Please enter a valid number.")
#             return redirect('interest_form')

#         # Filter all savings made in the specified month
#         savings_this_month = Savings.objects.filter(month__year=year, month__month=month)
#         # Count how many deductions were applied
#         count = 0  

#         for saving in savings_this_month:
#             member = saving.member

#             # Check if interest already deducted for this member and month
#             already_deducted = Interest.objects.filter(member=member, month=saving.month).exists()

#             if not already_deducted and saving.month_saving >= deduction_amount:
#                 # Preserve the original amount if not already saved
#                 if saving.original_amount is None:
#                     saving.original_amount = saving.month_saving

#                 # Deduct the specified amount
#                 saving.month_saving -= deduction_amount
#                 saving.save()

#                 # Record the deduction
#                 Interest.objects.create(member=member, month=saving.month,amount_deducted=deduction_amount)

#                 count += 1

#         if count:
#             messages.success(request, f"₦{deduction_amount} deducted from {count} members for {saving.month.strftime('%B %Y')}.")
#             return redirect('get_upload_interest')
#         else:
#             messages.info(request, f"No deductions made for {month}/{year}. Already deducted or amount below ₦{deduction_amount}.")
#         return redirect('interest_form')  
#     else:
#         return redirect('interest_form')


#========== distribute saving ===================

def distribute_savings(year, month, distribution_ratios=None):
    if distribution_ratios is None:
        distribution_ratios = {"loanable": Decimal("0.50"), "investment": Decimal("0.50")}

    savings_this_month = Savings.objects.filter(month__year=year, month__month=month)

    if not savings_this_month.exists():
        return "no_savings"

    distributed_count = 0

    for saving in savings_this_month:
        member = saving.member

        already_loanable = Loanable.objects.filter(member=member, month=saving.month).exists()
        already_investment = Investment.objects.filter(member=member, month=saving.month).exists()

        if already_loanable or already_investment:
            continue  # Skip this member, already distributed

        total = saving.month_saving

        loanable_amount = total * distribution_ratios.get("loanable", Decimal("0.00"))
        investment_amount = total * distribution_ratios.get("investment", Decimal("0.00"))

        Loanable.objects.create(
            member=member,
            month=saving.month,
            amount=loanable_amount,
            total_amount=total
        )
        Investment.objects.create(
            member=member,
            month=saving.month,
            amount=investment_amount,
            total_amount=total
        )

        distributed_count += 1

    return distributed_count

def distribute_savings_form(request):
    if request.method == "POST":
        month_str = request.POST.get("month")

        if not month_str:
            messages.error(request, "Please select a month.")
            return render(request, "main/distribute_savings_form.html")

        try:
            year, month = map(int, month_str.split("-"))
        except ValueError:
            messages.error(request, "Invalid month format.")
            return render(request, "main/distribute_savings_form.html")

        distribution_ratios = {"loanable": Decimal("0.50"), "investment": Decimal("0.50")}
        result = distribute_savings(year, month, distribution_ratios)

        if result == "exists":
            messages.warning(request, f"Savings distribution for {calendar.month_name[month]} {year} already exists.")
        elif result == "no_savings":
            messages.warning(request, f"No savings found for {calendar.month_name[month]} {year}.")
        else:
            messages.success(request, f"Savings for {calendar.month_name[month]} {year} distributed to {result} member(s).")

        return redirect("loanable_investment_months")

    return render(request, "main/distribute_savings_form.html")





def distribute_savings_view(request, year, month):
    # This view is no longer directly called from a URL, the distribution happens in the form view
    return HttpResponse(f"Distribution initiated for {calendar.month_name[month]} {year}. Check messages for status.")

#============== distribute saving end ===============


#============== loanable investment start ===============
def loanable_investment_months(request):
    """
    Collect all distinct months from Loanable and Investment tables,
    merge and sort them for display.
    """
    # Get distinct months from Loanable
    loanable_months = Loanable.objects.annotate(
        year=ExtractYear("month"), month_num=ExtractMonth("month")
    ).values("year", "month_num").distinct()

    # Get distinct months from Investment
    investment_months = Investment.objects.annotate(
        year=ExtractYear("month"), month_num=ExtractMonth("month")
    ).values("year", "month_num").distinct()

    # Combine and deduplicate months
    all_months_set = {
        (item["year"], item["month_num"]) for item in loanable_months
    } | {
        (item["year"], item["month_num"]) for item in investment_months
    }

    # Convert to sorted list of dicts with month names
    all_months = sorted(
        [
            {
                "year": year,
                "month_num": month,
                "month": calendar.month_name[month] if 1 <= month <= 12 else "Invalid"
            }
            for year, month in all_months_set
        ],
        key=lambda x: (x["year"], x["month_num"]),
        reverse=True
    )

    # Add pagination (10 items per page or adjust as needed)
    paginator = Paginator(all_months, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "main/loanable_investment_months.html", {"all_months": page_obj,   "page_obj": page_obj    })


def loanable_investment_details(request, year, month):
    # Filter by year and month
    loanables_qs = Loanable.objects.filter(month__year=year, month__month=month)
    investments_qs = Investment.objects.filter(month__year=year, month__month=month)

    # Totals
    total_loanable = loanables_qs.aggregate(total=Sum("amount"))["total"] or 0
    total_investment = investments_qs.aggregate(total=Sum("amount"))["total"] or 0

    # Paginate Loanables
    loanable_paginator = Paginator(loanables_qs, 100)
    loanable_page_number = request.GET.get("loanable_page")
    loanables = loanable_paginator.get_page(loanable_page_number)

    # Paginate Investments
    investment_paginator = Paginator(investments_qs, 100)
    investment_page_number = request.GET.get("investment_page")
    investments = investment_paginator.get_page(investment_page_number)

    context = {
        "loanables": loanables,
        "investments": investments,
        "month_name": calendar.month_name[month] if 1 <= month <= 12 else "Invalid",
        "year": year,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "loanable_page_obj": loanables,
        "investment_page_obj": investments,
    }

    return render(request, "main/loanable_investment_details.html", context)

def delete_month_entries(request, year, month):
    if request.method == "POST":
        Loanable.objects.filter(month__year=year, month__month=month).delete()
        Investment.objects.filter(month__year=year, month__month=month).delete()
        messages.success(request, f"Deleted records for {calendar.month_name[month]} {year}.")
    return redirect("loanable_investment_months")



#============== loanable investment end ===============
