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

    # moderation at scale
    path('bulk/', views.bulk_decide, name='bulk_decide'),
    path('reports/', views.agent_reports, name='agent_reports'),
    path('reports/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),
    path('users/<int:profile_id>/suspend/', views.suspend_user, name='suspend_user'),
    path('users/<int:profile_id>/reinstate/', views.lift_suspension,
         name='lift_suspension'),
    path('export/<str:what>.csv', views.agent_export, name='agent_export'),
]
