from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('approve/<int:property_id>/', views.approve_property, name='approve_property'),
    path('cancel_approval/<int:property_id>/', views.cancel_approval, name='cancel_approval'),

    # new in v2
    path('reject/<int:property_id>/', views.reject_property, name='reject_property'),
    path('feature/<int:property_id>/', views.toggle_feature, name='toggle_feature'),
    path('verify/<int:property_id>/', views.verify_documents, name='verify_documents'),
    path('stats/', views.agent_stats, name='agent_stats'),
    path('log/', views.agent_log, name='agent_log'),
    path('users/', views.agent_users, name='agent_users'),
    path('enquiries/', views.agent_enquiries, name='agent_enquiries'),
]
