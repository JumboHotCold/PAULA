"""
PauliBot Database Models
========================
Author: Senior Full-Stack Developer & DevOps Engineer
Purpose: Define database schema for user authentication and chat history storage

Models:
1. CustomUser - Extends Django's AbstractUser with student_id field
2. ChatHistory - Stores chat conversations linked to authenticated users
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def invalidate_changed_embedding(instance, kwargs, fields):
    """Invalidate exactly the text fields being persisted, including partial saves."""
    if not instance.pk:
        return
    update_fields = kwargs.get('update_fields')
    compared = set(fields) if update_fields is None else set(fields).intersection(update_fields)
    if not compared:
        return
    previous = type(instance).objects.filter(pk=instance.pk).values(*compared).first()
    if previous and any(previous[field] != getattr(instance, field) for field in compared):
        instance.embedding = None
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'embedding'}


class CustomUser(AbstractUser):
    """
    Custom User model for PauliBot authentication.
    
    Extends Django's AbstractUser to include student ID field.
    Passwords are automatically hashed by Django's authentication system.
    
    Fields:
        student_id: Unique identifier for students (e.g., "2024-00001")
        username: Login username (inherited from AbstractUser)
        password: Hashed password using PBKDF2 (inherited from AbstractUser)
        email: Student email address (inherited from AbstractUser)
        first_name: Student first name (inherited from AbstractUser)
        last_name: Student last name (inherited from AbstractUser)
    """
    student_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        default=None,
        help_text="Student ID number (e.g., 2024-00001). Leave blank for admin/staff accounts."
    )
    nickname = models.CharField(
        max_length=30, 
        null=True, 
        blank=True,
        help_text="Custom display name (max 30 chars)"
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        null=True, 
        blank=True,
        help_text="User profile picture"
    )
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-date_joined']
    
    def __str__(self):
        if self.student_id:
            return f"{self.student_id} - {self.username}"
        return f"[Admin] {self.username}"


class Conversation(models.Model):
    """
    Conversation grouping model.
    
    Groups multiple ChatHistory messages into a distinct session/thread.
    Allows for sidebar navigation similar to ChatGPT.
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='conversations',
        help_text="The user who owns this conversation"
    )
    title = models.CharField(
        max_length=255,
        default="New Chat",
        help_text="Title of the conversation (auto-generated or user-set)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    client_session_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['-updated_at']
        constraints = [models.UniqueConstraint(fields=['user', 'client_session_id'], name='unique_user_chat_session')]

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class ChatHistory(models.Model):
    """
    Chat history model for authenticated users.
    
    Stores conversation between students and PauliBot.
    Guest users do NOT have chat history saved (transient sessions).
    
    Fields:
        user: Foreign key to CustomUser (CASCADE delete)
        conversation: Link to parent Conversation (optional for now)
        message: User's input message
        response: Bot's generated response
        timestamp: Auto-generated timestamp for conversation ordering
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='chat_history',
        help_text="The authenticated user who sent this message"
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True,
        help_text="The conversation thread this message belongs to"
    )
    message = models.TextField(
        help_text="User's input message/question"
    )
    response = models.TextField(
        help_text="Bot's generated response"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this chat exchange occurred"
    )
    feedback = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[('positive', 'Positive'), ('negative', 'Negative')],
        help_text="Student feedback on this response (thumbs up/down)"
    )
    
    class Meta:
        verbose_name = "Chat History"
        verbose_name_plural = "Chat Histories"
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['conversation', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

# ==============================================================================
# KNOWLEDGE BASE MODELS (Phase 2 RAG)
# ==============================================================================

from pgvector.django import VectorField

class Location(models.Model):
    """
    University locations for PauliBot to reference.
    """
    name = models.CharField(max_length=255, help_text="Name of the location (e.g., 'Registrar')")
    description = models.TextField(help_text="Detailed description and where to find it")
    map_available = models.BooleanField(default=False, help_text="Is there a map for this location?")
    
    # AI Search embedding
    embedding = VectorField(dimensions=384, null=True, blank=True, help_text="Automatically generated vector embedding for semantic search")

    def save(self, *args, **kwargs):
        invalidate_changed_embedding(self, kwargs, ('name', 'description'))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class StaffMember(models.Model):
    """
    University staff directory.
    """
    name = models.CharField(max_length=255, help_text="Full Name with title (e.g., 'Sr. Marie Rosanne Mallillin, SPC')")
    position = models.CharField(max_length=255, help_text="Official Job Title")
    office = models.CharField(max_length=255, help_text="Where is their office located?")
    
    # AI Search embedding
    embedding = VectorField(dimensions=384, null=True, blank=True)

    def save(self, *args, **kwargs):
        invalidate_changed_embedding(self, kwargs, ('name', 'position', 'office'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.position}"

class FAQ(models.Model):
    """
    General university FAQs (Admissions, Academics, etc.).
    """
    category = models.CharField(max_length=100, help_text="Category (e.g., 'Admissions', 'Tuition')")
    question = models.CharField(max_length=500, help_text="The question or topic")
    answer = models.TextField(help_text="The official answer")
    
    # Source tracking for knowledge priority (Office > Website > Handbook)
    SOURCE_TYPES = [
        ('office', 'Office-Submitted'),    # From admin/dept letters (Highest authority)
        ('handbook', 'Student Handbook'),   # From Handbook.pdf OCR (Foundational policies)
        ('website', 'Website'),            # From spus.edu.ph scrapes (Current facts)
        ('curated', 'Curated/Manual'),     # From data.py or admin panel
    ]
    source_type = models.CharField(
        max_length=20,
        default='curated',
        choices=SOURCE_TYPES,
        help_text="Origin of this entry: office-submitted, handbook, website, or curated"
    )
    source_office = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="Office/Department that provided this (e.g. 'Registrar', 'Finance', 'CEIT', 'CHS')"
    )

    # AI Search embedding
    embedding = VectorField(dimensions=384, null=True, blank=True)

    def save(self, *args, **kwargs):
        invalidate_changed_embedding(self, kwargs, ('category', 'question', 'answer'))
        super().save(*args, **kwargs)

    def __str__(self):
        prefix = f"[{self.source_office}] " if self.source_office else f"[{self.get_source_type_display()}] "
        return f"{prefix}{self.question}"


class WebResource(models.Model):
    """
    Official institutional web resources scraped from spus.edu.ph.
    Used by PauliBot RAG to provide verified answers with citation URLs.
    """
    title = models.CharField(max_length=255, help_text="Page or Section title")
    url = models.URLField(max_length=500, help_text="Official SPUS URL")
    category = models.CharField(max_length=100, default="General", help_text="Category (e.g., 'Admissions', 'Academics', 'TVET', 'About')")
    content = models.TextField(help_text="Extracted text content from the webpage")
    last_scraped = models.DateTimeField(auto_now=True)
    
    # AI Search embedding
    embedding = VectorField(dimensions=384, null=True, blank=True, help_text="Vector embedding for semantic search")

    class Meta:
        verbose_name = "Web Resource"
        verbose_name_plural = "Web Resources"
        ordering = ['category', 'title']

    def save(self, *args, **kwargs):
        invalidate_changed_embedding(self, kwargs, ('category', 'title', 'content'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.category}] {self.title}"



# ==============================================================================
# ADMIN DASHBOARD MODELS
# ==============================================================================

class StudentNeed(models.Model):
    """
    Tracks flagged student cases for the institutional admin dashboard.
    """
    NEED_TYPE_CHOICES = [
        ('Financial', 'Financial'),
        ('Academic', 'Academic'),
        ('Enrollment', 'Enrollment'),
        ('Mental Health', 'Mental Health'),
    ]
    URGENCY_CHOICES = [
        ('Critical', 'Critical'),
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]

    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='student_needs',
        help_text="The student this need case is about"
    )
    need_type = models.CharField(max_length=20, choices=NEED_TYPE_CHOICES)
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='Medium')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Open')
    assigned_advisor = models.CharField(max_length=100, default='Unassigned')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student Need"
        verbose_name_plural = "Student Needs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.student_id} — {self.need_type} ({self.urgency})"

class Announcement(models.Model):
    """
    Campus-wide announcements created by admins and displayed to all users (Guests/Students).
    """
    title = models.CharField(max_length=200, help_text="Headline or Title of the announcement")
    content = models.TextField(help_text="Detailed message of the announcement")
    is_active = models.BooleanField(default=True, help_text="Toggle to show/hide this announcement")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-created_at']

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"[{status}] {self.title}"

