from django.urls import path 
from .import views 

urlpatterns = [
    path('admin_dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('summary/',views.summary_view,name='summary'),
    path('all_member_saving_search/',views.all_member_saving_search,name='all_member_saving_search'),
    path('get_upload_interest/',views.get_upload_interest,name='get_upload_interest'),
    path('get_upload_interest_details/<int:month>/',views.get_upload_interest_details,name='get_upload_interest_details'),
    path('delete_interest/<int:year>/<int:month>/', views.delete_interest_saving, name='delete_interest_saving'),
    path('financial_list/', views.list_financial_summaries, name='financial_list'),
     path('financial-summary/delete/<int:pk>/', views.delete_financial_summary, name='delete_financial_summary'),
   
]