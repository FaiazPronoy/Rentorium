from django.urls import path

from . import views

urlpatterns = [
    path('signup', views.signup, name='signup'),
    path('signin', views.signin, name='signin'),
    path('signout', views.signout, name='signout'),
    path('profile', views.profile, name='profile'),
    path('edit-profile', views.edit_profile, name='edit_profile'),
    path('delete-account', views.delete_account, name='delete_account'),

    # new in v2
    path('dashboard/', views.dashboard, name='dashboard'),
    path('change-password/', views.change_password, name='change_password'),
    path('become-owner/', views.become_owner, name='become_owner'),
    path('people/<int:pk>/', views.public_profile, name='public_profile'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read/<int:pk>/', views.read_notification, name='read_notification'),
    path('notifications/read-all/', views.read_all_notifications, name='read_all_notifications'),
]
