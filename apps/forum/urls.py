from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.index, name="index"),
    path("c/<slug:slug>/", views.category, name="category"),
    path("c/<slug:slug>/novo/", views.topic_create, name="topic_create"),
    path("t/<int:pk>/<slug:slug>/", views.topic, name="topic"),
    path("t/<int:pk>/responder/", views.post_create, name="post_create"),
]
