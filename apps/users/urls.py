from django.contrib import admin
from django.urls import path
from .views import CustomTokenRefreshView, LoginAPIView, LogoutView, RegistrationView, \
    RequestPasswordResetEmail,SetNewPasswordAPIView

urlpatterns = [
    path("register/",RegistrationView.as_view(),name="register"),
    path("login/",LoginAPIView.as_view(),name="login"),
    path("refresh/",CustomTokenRefreshView.as_view(),name="refresh"),
    path("logout/",LogoutView.as_view(),name="logout"),
    path("forgot-password/",RequestPasswordResetEmail.as_view(),name="reset-password"),
    path("password-reset-complete",SetNewPasswordAPIView.as_view(),name="reset-password"),
]
