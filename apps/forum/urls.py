from django.urls import path

from . import views

app_name = "forum"

# Ordem importa. O Django casa a primeira rota que bater, e `<slug:slug>` casa
# qualquer palavra — inclusive as que são ação, não slug. Com a rota genérica
# antes, `/t/1/responder/` era lida como o tópico 1 com slug "responder", e a
# view de tópico respondia 301 para a URL "correta". Resultado: responder não
# funcionava, e sem erro nenhum — só uma página que recarregava.
#
# Regra: rota específica antes de rota com parâmetro livre.
urlpatterns = [
    path("", views.index, name="index"),
    path("c/<slug:slug>/novo/", views.topic_create, name="topic_create"),
    path("c/<slug:slug>/", views.category, name="category"),
    path("t/<int:pk>/responder/", views.post_create, name="post_create"),
    path("t/<int:pk>/<slug:slug>/", views.topic, name="topic"),
]
