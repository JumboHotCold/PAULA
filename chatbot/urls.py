"""
PauliBot URL Configuration
===========================
URL patterns for chatbot application endpoints.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Frontend Pages
    path('', views.landing_view, name='landing'),
    path('chat/', views.chat_view, name='chat_view'),
    path('register/', views.register_page, name='register_page'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_page, name='logout_page'),

    # API Endpoints (AJAX)
    path('api/health/live', views.health_live, name='health_live'),
    path('api/health/ready', views.health_ready, name='health_ready'),
    path('api/chat', views.chat_api, name='chat_api'),
    path('api/history', views.get_chat_history, name='history'), # Legacy support
    path('api/conversations', views.conversation_list, name='conversation_list'),
    path('api/conversations/<int:conversation_id>', views.conversation_detail, name='conversation_detail'),
    path('api/feedback/<int:chat_id>', views.submit_feedback, name='submit_feedback'),
    
    # API Auth (Optional/Legacy support)
    path('api/register', views.register_user, name='api_register'),
    path('api/login', views.login_user, name='api_login'),
    path('api/logout', views.logout_user, name='api_logout'),
    path('api/session', views.session_status, name='api_session'),

    # Admin Dashboard API
    path('api/admin/campus-pulse/', views.admin_campus_pulse, name='admin_campus_pulse'),
    path('api/admin/trending-confusion/', views.admin_trending_confusion, name='admin_trending_confusion'),
    path('api/admin/metrics/', views.admin_metrics, name='admin_metrics'),
    path('api/admin/student-needs/', views.admin_student_needs, name='admin_student_needs'),
    path('api/admin/student-needs/<int:pk>/', views.admin_student_need_detail, name='admin_student_need_detail'),
    path('api/admin/reports/data/', views.admin_reports_data, name='admin_reports_data'),
    path('api/admin/reports/print/', views.admin_reports_print, name='admin_reports_print'),
    path('api/admin/reports/export/csv/', views.admin_reports_export_csv, name='admin_reports_export_csv'),
    path('api/admin/reports/export/pdf/', views.admin_reports_export_pdf, name='admin_reports_export_pdf'),
    
    # Public API
    path('api/announcements', views.get_announcements, name='get_announcements'),
    path('api/profile', views.update_profile, name='api_profile'),
    
    # Campus Navigation API
    path('api/navigation/route/', views.calculate_campus_route, name='calculate_campus_route'),
]
