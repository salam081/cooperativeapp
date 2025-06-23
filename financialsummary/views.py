import calendar
from decimal import Decimal
from django.shortcuts import render,redirect,get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib.auth.decorators import login_required
from .models import FinancialSummary
from accounts.models import *
from main.models import *
from memberapp.models import *
from consumable.models import *
from .models import *
from decimal import Decimal,DecimalException
from datetime import datetime
from django.db import transaction
from datetime import timedelta
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from django.contrib import messages


def is_admin(user):
    return user.is_staff

@login_required
# @user_passes_test(is_admin)
def admin_dashboard(request):
    # Example data retrieval (adjust as needed for your dashboard)
    total_members = Member.objects.count()
    total_loans = LoanRequest.objects.count()
    # total_loan_amount = LoanRequest.objects.filter(status='approved').aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    pending_loans = LoanRequest.objects.filter(status='pending').count()
    rejected_loans = LoanRequest.objects.filter(status='rejected').count()
    loan_types = LoanType.objects.all()
    # total_consumable = ConsumableRequestDetail.objects.count()
    pending_consumable = ConsumableRequest.objects.filter(status='Pending').count()
    # total_consumable_amonth = ConsumableRequestDetail.objects.filter(request__status='Approved').aggregate(total=Sum('approved_amount'))['total'] or 0
   
    def get_monthly_totals(queryset, value_field):
        return (
            queryset
            .annotate(year=ExtractYear("month"), month_num=ExtractMonth("month"))
            .values("year", "month_num")
            .annotate(total=Sum(value_field, default=Decimal('0.00')))
            .order_by("-year", "-month_num")
        )

    def format_months(data):
        return [
            {
                "year": row["year"],
                "month_num": row["month_num"],
                "month": calendar.month_name[row["month_num"]],
                "total": Decimal(row["total"] or '0.00'),
            }
            for row in data
        ]
    
    savings_monthly = format_months(get_monthly_totals(Savings.objects.all(), "month_saving"))
    interest_monthly = format_months(get_monthly_totals(Interest.objects.all(), "amount_deducted"))
    loanable_monthly = format_months(get_monthly_totals(Loanable.objects.all(), "amount"))
    investment_monthly = format_months(get_monthly_totals(Investment.objects.all(), "amount"))

    # Total calculations (no pagination here, just sums)
    total_savings = Decimal(sum(item["total"] for item in savings_monthly))
    total_interest = Decimal(sum(item["total"] for item in interest_monthly))
    total_loanable = Decimal(sum(item["total"] for item in loanable_monthly))
    total_investment = Decimal(sum(item["total"] for item in investment_monthly))

    grand_total = total_savings + total_interest #+ total_loanable + total_investment
    
    investment_loanable = total_loanable + total_investment

    try:
        # Get the latest summary from the DB
        latest_summary = FinancialSummary.objects.order_by('-created_at').first()
        if not latest_summary or latest_summary.grand_total != grand_total:
            # Only save if it's new or changed
            FinancialSummary.objects.create(
                total_savings=total_savings, total_interest=total_interest,
                total_loanable=total_loanable, total_investment=total_investment,
                grand_total=grand_total,user=request.user
            )
            print(f"New FinancialSummary saved. Grand Total: ₦{grand_total}")
        else:
            print(f"No change detected. Grand Total (₦{grand_total}) matches the latest saved summary.")
        print(f"FinancialSummary snapshot saved automatically for user {request.user.username}")
    except Exception as e:
        print(f"ERROR: Failed to automatically save FinancialSummary snapshot for user {request.user.username}. Error: {e}")

    context = {
        'total_members': total_members,
        'total_loans': total_loans,
        # 'total_loan_amount': total_loan_amount,
        'pending_loans': pending_loans,
        'rejected_loans': rejected_loans,
        'loan_types': loan_types, 

        # 'total_consumable':total_consumable,
        'pending_consumable':pending_consumable,
        "total_savings": total_savings,
        "total_interest": total_interest,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "grand_total": grand_total,

        'investment_loanable':investment_loanable
    }
    return render(request, 'admin_dashboard.html', context)



@login_required 
def summary_view(request):
    def get_monthly_totals(queryset, value_field):
        return (
            queryset
            .annotate(year=ExtractYear("month"), month_num=ExtractMonth("month"))
            .values("year", "month_num")
            .annotate(total=Sum(value_field, default=Decimal('0.00')))
            .order_by("-year", "-month_num")
        )

    def format_months(data):
        return [
            {
                "year": row["year"],
                "month_num": row["month_num"],
                "month": calendar.month_name[row["month_num"]],
                "total": Decimal(row["total"] or '0.00'),
            }
            for row in data
        ]

    # Use .all() or apply necessary filters to base querysets
    savings_monthly = format_months(get_monthly_totals(Savings.objects.all(), "month_saving"))
    interest_monthly = format_months(get_monthly_totals(Interest.objects.all(), "amount_deducted"))
    loanable_monthly = format_months(get_monthly_totals(Loanable.objects.all(), "amount"))
    investment_monthly = format_months(get_monthly_totals(Investment.objects.all(), "amount"))

    # Paginate the lists
    def paginate_data(data, page_size=12):
        paginator = Paginator(data, page_size)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        return page_obj

    savings_page = paginate_data(savings_monthly)
    interest_page = paginate_data(interest_monthly)
    loanable_page = paginate_data(loanable_monthly)
    investment_page = paginate_data(investment_monthly)

    # Total calculations (no pagination here, just sums)
    total_savings = Decimal(sum(item["total"] for item in savings_monthly))
    total_interest = Decimal(sum(item["total"] for item in interest_monthly))
    total_loanable = Decimal(sum(item["total"] for item in loanable_monthly))
    total_investment = Decimal(sum(item["total"] for item in investment_monthly))
    grand_total = total_savings + total_interest #+ total_loanable + total_investment

    # --- Existing Per-member totals ---
    member_savings = Member.objects.annotate(
        aggregated_savings=Sum('savings__month_saving', default=Decimal('0.00'))
    ).order_by('-aggregated_savings')
    print(member_savings,'member_savings')
    # Optimized member interest fetching slightly
    member_interest_data = Member.objects.annotate(
        total_interest=Sum('interest__amount_deducted', default=Decimal('0.00'))
    )
    member_interest = {m.id: m.total_interest for m in member_interest_data}

    context = {
        "savings_page": savings_page,
        "interest_page": interest_page,
        "loanable_page": loanable_page,
        "investment_page": investment_page,
        "total_savings": total_savings,
        "total_interest": total_interest,
        "total_loanable": total_loanable,
        "total_investment": total_investment,
        "grand_total": grand_total,
        "member_savings": member_savings,
        "member_interest": member_interest,
    }

    return render(request, "financial/summary2.html", context)

def list_financial_summaries(request):
    summaries = FinancialSummary.objects.select_related('user').all()
    context = {'summaries': summaries}
    return render(request, 'financial/summary_list.html', context)


def delete_financial_summary(request, pk):
    summary = get_object_or_404(FinancialSummary, pk=pk)
    if request.method == 'POST':
        summary.delete()
        messages.success(request, 'Financial summary deleted successfully.')
    return redirect('financial_list')  


def filter_requests(datefrom, dateto, ):
    filtered_requests = Savings.objects.all() 

    if datefrom:
        filtered_requests = filtered_requests.filter(month__gte=datefrom)
    if dateto:
        filtered_requests = filtered_requests.filter(month__lte=dateto)
   
    return filtered_requests  


@login_required
def all_member_saving_search(request):
    datefrom = request.GET.get('datefrom')
    dateto = request.GET.get('dateto')
    status = request.GET.get('status')

    member = None

    if datefrom or dateto:
        filtered = filter_requests(datefrom, dateto)
        paginator = Paginator(filtered, 100)  # 50 per page
        page_number = request.GET.get('page')
        member = paginator.get_page(page_number)

    context = {
        'member': member,
        'status': status,
        'datefrom': datefrom,
        'dateto': dateto,
    }

    return render(request, 'all_member_saving_search.html', context)


def get_upload_interest(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    interest = Interest.objects.all()

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            interest = interest.filter(month__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            interest = interest.filter(month__lte=date_to_parsed)
        except ValueError:
            pass

    months = interest.annotate(
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
    paginator = Paginator(data, 100) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "get_upload_interest.html", {"page_obj": page_obj,"date_from": date_from,"date_to": date_to})


def get_upload_interest_details(request, month):
    interest_list = Interest.objects.filter(month__month=month)
    paginator = Paginator(interest_list, 100)  # Show 10 items per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request,"get_upload_interest_details.html",{"page_obj": page_obj})


def delete_interest_saving(request, year, month):
    if request.method == "POST":
        interest_qs = Interest.objects.select_related("member").filter(month__year=year, month__month=month)
        
        affected_members = {interest.member for interest in interest_qs}
        interest_qs.delete()

        for member in affected_members:
            member.update_total_savings()  # Optimize this method if it's slow

        messages.success(request, f"Deleted interest savings for {calendar.month_name[month]} {year}.")

    return redirect("get_upload_interest")






