from . import views
from django.urls import path
from django.contrib import admin


urlpatterns = [
    path('', views.signin, name = "signin"),
    path('signup', views.signup, name = "signup"),
    path('signout', views.signout, name = "signout"),
    path('base', views.base, name = "base"),
    path('profile', views.profile, name = "profile"),
    path('edit-profile', views.edit_profile, name = "edit_profile"),
    path('delete-account', views.delete_account, name = "delete_account"),

]
