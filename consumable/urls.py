from django.urls import path 

from . import views

urlpatterns = [
    path('add_consumables_items/', views.add_consumables_items, name='add_consumables_items'),
    path('delete_item/<id>/', views.delete_item, name='delete_item'),
    path('consumable_items/', views.consumable_items, name='consumable_items'),
    path('requests/', views.consumable_requests_list, name='consumable_requests_list'),
    path('requests/<int:request_id>/approve/', views.approve_consumable_request, name='approve_consumable_request'),
    path('requests/<int:request_id>/decline/', views.decline_consumable_request, name='decline_consumable_request'),
    path('upload_consumable_payment/', views.upload_consumable_payment, name='upload_consumable_payment'),
    path('add_single_consumable_payment/', views.add_single_consumable_payment, name='add_single_consumable_payment'),
    path('staff/edit-request/<int:request_id>/', views.admin_edit_consumable_request, name='admin_edit_consumable_request'),
    path('consumable_requests_by_month',views.consumable_requests_by_month,name='consumable_requests_by_month'),
    # urls.py
    path('consumable_details/<month>/', views.consumable_details, name='consumable_details'),
    path('consumable_repayments_list', views.consumable_repayments_list, name='consumable_repayments_list'),
   

]
