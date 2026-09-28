"""Top level URL map for Rentorium."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from authentication.views import password_reset_confirm, signin

urlpatterns = [
    path('', include('basic.urls')),
    path('admin/', admin.site.urls),
    path('account/', include('authentication.urls')),
    path('property/', include('property.urls')),
    path('agents/', include('Agents.urls')),

    path('login/', signin, name='login'),

    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='password_reset.html',
             email_template_name='email/password_reset_email.txt',
             subject_template_name='email/password_reset_subject.txt',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/',
         password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='password_reset_complete.html'),
         name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = 'basic.views.handler404'
handler500 = 'basic.views.handler500'
