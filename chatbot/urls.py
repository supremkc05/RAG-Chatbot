from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('chat/<str:session_id>/', views.ChatView.as_view(), name='chat'),
    path('api/create-session/', views.CreateSessionView.as_view(), name='create_session'),
    path('api/ask/<str:session_id>/', views.AskQuestionView.as_view(), name='ask_question'),
    path('api/status/<str:session_id>/', views.SessionStatusView.as_view(), name='session_status'),
    path('api/history/<str:session_id>/', views.ChatHistoryView.as_view(), name='chat_history'),
]
