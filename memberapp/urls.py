from django.urls import path
from .import views

urlpatterns = [
    path('requests-disabled/',views. disabled_requests_page, name='disabled_requests_page'),
    path('member_dashboard',views.member_dashboard,name="member_dashboard"),
    # path('loan_request/', views.loan_request_view, name='loan_request'),
    path('loan-request/', views.loan_request_view, name='loan_request'),
    path('ajax/load-bank-code/', views.ajax_load_bank_code, name='ajax_load_bank_code'),
    path('member_request_consumable/', views.member_request_consumable, name='member_request_consumable'),
    path('edit-request/<int:request_id>/', views.edit_consumable_request, name='edit_consumable_request'),
    path('member_savings',views.member_savings,name='member_savings')
   
    
]