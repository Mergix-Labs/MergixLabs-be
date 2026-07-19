from django.urls import re_path

from .consumers import ChatFintechConsumer

websocket_urlpatterns = [
    re_path(r"^ws/fintech-chatbot/$", ChatFintechConsumer.as_asgi()),
]
