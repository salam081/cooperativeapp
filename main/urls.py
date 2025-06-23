from django.urls import path
from .import views

urlpatterns = [
    path('index',views.index,name="index"),
    path('search_member_savings/', views.search_member_for_savings, name='search_member'),
    path('member/<int:id>/add_savings/', views.add_individual_member_savings, name='add_individual_savings'),
    path('upload_saving',views.upload_savings,name="upload_savings"),
    path("get_upload_savings", views.get_upload_savings, name="get_upload_savings"),
    path('get_upload_details/<int:month>/', views.get_upload_details, name='get_upload_details'),
    path('delete_saving/<int:month>/', views.delete_saving, name='delete_saving'),

    path("interest_form/", views.interest_form_view, name='interest_form'),
    path('deduct_interest/', views.deduct_monthly_interest, name='deduct_interest'),

    path('distribute/', views.distribute_savings_form, name='distribute_savings'),
    path('distribute_savings/<int:year>/<int:month>/', views.distribute_savings_view, name='distribute_savings'),
    path("loanable_investment_months/", views.loanable_investment_months, name='loanable_investment_months'),
    path('details/<int:year>/<int:month>/', views.loanable_investment_details, name='loanable_investment_details'),
    path("delete/month/<int:year>/<int:month>/", views.delete_month_entries, name="delete_month_entries"),


    
]