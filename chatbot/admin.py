"""
PauliBot Admin Configuration
==============================
Uses django-unfold for a modern, SPUS-branded admin panel.
Faculty/Staff can manage the Knowledge Base (Locations, Staff, FAQs) here.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin

from .models import CustomUser, Conversation, ChatHistory, Location, StaffMember, FAQ, WebResource, StudentNeed, Announcement


# ==============================================================================
# USER MANAGEMENT
# ==============================================================================

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('username', 'student_id', 'email', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'student_id', 'email')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Student Info', {'fields': ('student_id',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Student Info', {'fields': ('student_id',)}),
    )


# ==============================================================================
# CHAT MANAGEMENT
# ==============================================================================

@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'user__username')


@admin.register(ChatHistory)
class ChatHistoryAdmin(ModelAdmin):
    list_display = ('user', 'conversation', 'feedback', 'timestamp')
    list_filter = ('feedback', 'timestamp')
    search_fields = ('user__username', 'message')
    readonly_fields = ('timestamp',)


# ==============================================================================
# KNOWLEDGE BASE (Faculty/Staff Managed)
# ==============================================================================

@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ('name', 'map_available')
    search_fields = ('name', 'description')
    list_filter = ('map_available',)


@admin.register(StaffMember)
class StaffMemberAdmin(ModelAdmin):
    list_display = ('name', 'position', 'office')
    search_fields = ('name', 'position')


@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    list_display = ('question', 'category', 'source_type', 'source_office')
    list_filter = ('source_type', 'source_office', 'category')
    search_fields = ('question', 'answer', 'source_office')


@admin.register(WebResource)
class WebResourceAdmin(ModelAdmin):
    list_display = ('title', 'category', 'url', 'last_scraped')
    list_filter = ('category', 'last_scraped')
    search_fields = ('title', 'content', 'url')
    readonly_fields = ('last_scraped',)



# ==============================================================================
# ADMIN DASHBOARD
# ==============================================================================

@admin.register(StudentNeed)
class StudentNeedAdmin(ModelAdmin):
    list_display = ('student', 'need_type', 'urgency', 'status', 'assigned_advisor', 'created_at')
    list_filter = ('urgency', 'need_type', 'status')
    search_fields = ('student__student_id', 'student__username', 'description')
    list_editable = ('status', 'assigned_advisor')

@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
