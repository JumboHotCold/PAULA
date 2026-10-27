"""
PauliBot API Serializers
=========================
Author: Senior Full-Stack Developer & DevOps Engineer
Purpose: Django REST Framework serializers for API request/response validation

Serializers:
1. UserRegistrationSerializer - Validates new user registration
2. UserLoginSerializer - Validates login credentials
3. ChatHistorySerializer - Formats chat history for API responses
"""

from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import CustomUser, ChatHistory, Conversation


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration endpoint.
    
    Validates student_id, username, password, and email.
    Password is write-only and automatically hashed by Django.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Password (will be hashed automatically)"
    )
    
    class Meta:
        model = CustomUser
        fields = ['id', 'student_id', 'username', 'email', 'password', 'first_name', 'last_name']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        """
        Create new user with hashed password.
        
        Uses Django's create_user() method which automatically hashes
        the password using PBKDF2 algorithm.
        """
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            student_id=validated_data['student_id'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login endpoint.
    
    Validates identifier (Student ID or Username) and password against database.
    Accepts both 'username' and 'student_id' keys for the identifier to ensure compatibility.
    """
    username = serializers.CharField(required=False)
    student_id = serializers.CharField(required=False)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, data):
        """
        Validate credentials using Django's authenticate() method.
        """
        # Accept either 'username' or 'student_id' as the identifier
        identifier = data.get('username') or data.get('student_id')
        password = data.get('password')
        
        if identifier and password:
            # Django's authenticate() will try our StudentIDBackend first (student_id check)
            # and then falls back to ModelBackend (username check).
            user = authenticate(username=identifier, password=password)
            if user is None:
                raise serializers.ValidationError("Invalid credentials. Please check your details.")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")
            data['user'] = user
        else:
            raise serializers.ValidationError("Must include an identifier (Student ID or Username) and password.")
        
        return data


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for conversation list.
    """
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'is_active', 'client_session_id']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for chat history retrieval endpoint.
    
    Formats chat history with user details and timestamps.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    student_id = serializers.CharField(source='user.student_id', read_only=True)
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True, allow_null=True)
    
    class Meta:
        model = ChatHistory
        fields = ['id', 'username', 'student_id', 'conversation_id', 'message', 'response', 'feedback', 'timestamp']
        read_only_fields = ['id', 'username', 'student_id', 'timestamp', 'conversation_id']
