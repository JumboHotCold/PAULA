"""
PauliBot Views
==============
Handles both frontend HTML rendering and API endpoints.
"""

import json
import math
from collections.abc import Mapping
from uuid import UUID
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
import re
from django.utils import timezone
from django.db import DatabaseError

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from .api_errors import failure

from .logic import PauliBotLogic
from .intents import guest_clarification_history
from .conversation_context import bounded_history
from .context_tokens import decode_dialogue_state, encode_context
from .suggestions import bounded_questions, response_suggestions
from .models import ChatHistory, CustomUser, Conversation, StudentNeed, Announcement
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    ChatHistorySerializer,
    ConversationSerializer
)
from .reports import (
    get_analytics_summary_data,
    generate_analytics_csv,
    generate_analytics_pdf,
    render_print_html
)

# Initialize bot logic engine
bot = PauliBotLogic()


@require_GET
def health_live(request):
    return JsonResponse({'live': True})


@require_GET
def health_ready(request):
    from .health import service_readiness
    state = service_readiness()
    return JsonResponse(state, status=200 if state['ready'] else 503)

# ==============================================================================
# FRONTEND VIEWS (HTML PAGES)
# ==============================================================================

@ensure_csrf_cookie
def landing_view(request):
    """
    Renders the landing page with login/register options.
    Redirects authenticated users mostly to chat, but allows access if explicitly requested.
    """
    if request.user.is_authenticated:
        return redirect('chat_view')
    return render(request, 'chatbot/landing.html')

@ensure_csrf_cookie
def register_page(request):
    """
    Renders registration page and handles form submission.
    """
    if request.user.is_authenticated:
        return redirect('chat_view')
        
    if request.method == 'POST':
        # Create a mutable copy of request.data for serializer
        data = request.POST.copy()
        serializer = UserRegistrationSerializer(data=data)
        
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            return redirect('chat_view')
        else:
            # Pass errors to template
            error_msg = next(iter(serializer.errors.values()))[0]
            return render(request, 'chatbot/register.html', {'error': error_msg})
            
    return render(request, 'chatbot/register.html')

def login_page(request):
    """
    Handles login form submission from landing page.
    """
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        password = request.POST.get('password')
        
        user = authenticate(request, username=student_id, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('chat_view')
        else:
            return render(request, 'chatbot/landing.html', {'error': 'Invalid Student ID or password'})
            
    return redirect('landing')

def logout_page(request):
    """
    Logs out user and redirects to landing page.
    """
    logout(request)
    return redirect('landing')

@ensure_csrf_cookie
def chat_view(request):
    """
    Renders the main chat interface.
    - Authenticated: Loads chat history
    - Guest: Loads empty chat
    """
    context = {}
    
    # HYBRID ACCESS LOGIC
    # A page opens an empty thread. Selecting a sidebar conversation loads only
    # that owned thread; never concatenate every past conversation in one view.
    context['chat_history'] = []
        
    return render(request, 'chatbot/chat.html', context)

# ==============================================================================
# API ENDPOINTS (AJAX/JSON)
# ==============================================================================

@api_view(['POST'])
def register_user(request):
    """API Endpoint for registration (JSON)"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': 'User registered successfully',
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login_user(request):
    """API Endpoint for login (JSON)"""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        return Response({
            'message': 'Login successful',
            'name': user.first_name or user.username,
            'is_superuser': user.is_superuser,
            'student_id': user.student_id,
            'account_id': user.student_id or user.username,
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def logout_user(request):
    """API Endpoint for logout (JSON)"""
    logout(request)
    return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


@ensure_csrf_cookie
@api_view(['GET'])
def session_status(request):
    """The browser restores identity from Django, not localStorage alone."""
    if not request.user.is_authenticated:
        return Response({'authenticated':False})
    return Response({'authenticated':True, 'id':request.user.student_id or request.user.username,
                     'is_superuser':request.user.is_superuser})

@api_view(['GET'])
@login_required
def get_chat_history(request):
    """API Endpoint to get chat history (JSON)"""
    chat_history = ChatHistory.objects.filter(user=request.user)
    serializer = ChatHistorySerializer(chat_history, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
@login_required
def conversation_list(request):
    """
    List all conversations or create a new one.
    """
    if request.method == 'GET':
        conversations = Conversation.objects.filter(user=request.user, is_active=True).order_by('-updated_at')
        serializer = ConversationSerializer(conversations, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        # Create new conversation
        conversation = Conversation.objects.create(user=request.user)
        return Response({
            'message': 'Conversation created',
            'conversation_id': conversation.id,
            'title': conversation.title
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@login_required
def conversation_detail(request, conversation_id):
    """
    Get messages for a specific conversation or delete it.
    """
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user, is_active=True)
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        messages = conversation.messages.all().order_by('timestamp')
        serializer = ChatHistorySerializer(messages, many=True)
        return Response(serializer.data)
    
    elif request.method == 'DELETE':
        conversation.is_active = False  # Soft delete
        conversation.save()
        return Response({'message': 'Conversation deleted'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def chat_api(request):
    """
    Hybrid Access Chat Endpoint
    Handles actual logic for both Authenticated and Guest users.
    Supports Conversation History.
    """
    try:
        # Let DRF parse JSON/form bodies. Lists/scalars are not named fields.
        data = request.data
        if not isinstance(data, Mapping):
            return failure('invalid_request', 400)
            
        user_message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        if conversation_id not in (None, ''):
            if isinstance(conversation_id, bool) or not isinstance(conversation_id, (str, int)) or not str(conversation_id).isdecimal() or int(conversation_id) <= 0:
                return failure('invalid_conversation', 400)
            conversation_id = int(conversation_id)
        # Fail closed: possession of an old session cookie alone is never
        # sufficient to opt a chat request into permanent history.
        mode = data.get('mode', 'guest')
        if mode not in ('guest', 'authenticated'):
            return Response({'error':'Invalid chat mode.'}, status=400)
        persist = request.user.is_authenticated and mode == 'authenticated'
        if mode == 'authenticated' and not request.user.is_authenticated:
            return Response({'error':'Please log in again to save this conversation.'}, status=401)
        expected_account = data.get('account_id')
        if persist and expected_account is not None and str(expected_account) != str(request.user.student_id or request.user.username):
            return Response({'error':'The signed-in account changed. Please log in again.'}, status=401)
        client_session_id = data.get('chat_session_id')
        try:
            client_session_id = UUID(str(client_session_id)) if client_session_id else None
        except ValueError:
            return Response({'error':'Invalid chat session identifier.'}, status=400)
        
        if not isinstance(user_message, str) or not user_message.strip() or len(user_message) > 2000:
            return failure('invalid_message', 400)

        conversation = None
        # Resolve ownership and a stable client chat BEFORE reading history.
        # A missing ID no longer creates a fresh sidebar item on every prompt.
        if persist:
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=request.user, is_active=True)
                except Conversation.DoesNotExist:
                    return Response({'error':'Conversation not found.'}, status=404)
            elif client_session_id:
                conversation = Conversation.objects.filter(user=request.user, client_session_id=client_session_id).first()
                if conversation is not None and not conversation.is_active:
                    return Response({'error':'This conversation was deleted. Start a new chat.'}, status=409)
                if conversation is None:
                    conversation, _ = Conversation.objects.get_or_create(user=request.user, client_session_id=client_session_id,
                        defaults={'title':user_message[:30] + ('...' if len(user_message) > 30 else '')})
                conversation_id = conversation.id
            else:
                # Compatibility for older clients. New clients use the UUID
                # above, giving separate tabs/New Chat independent sessions.
                session = getattr(request, 'session', None)
                previous_id = session.get('paula_conversation_id') if session is not None else None
                if previous_id:
                    conversation = Conversation.objects.filter(id=previous_id, user=request.user, is_active=True).first()
                    if conversation is not None:
                        conversation_id = conversation.id

        # Process query with Logic Engine
        # A bounded transient clarification also covers authenticated clients
        # that have not retained their first returned conversation ID. It is
        # used only for routing; persisted history from an owned thread wins.
        history_msgs = bounded_history(data.get('history'))
        context_anchor = None
        if conversation_id and persist:
            # Fetch last 5 interactions (10 messages total) for context to stay within token limits
            past_chats = ChatHistory.objects.filter(
                conversation_id=conversation_id, 
                user=request.user,
                conversation__is_active=True,
            ).order_by('-timestamp')[:4]
            history_msgs = []
            
            # Reverse to get chronological order [ oldest -> newest ]
            for chat in reversed(past_chats):
                context_anchor = getattr(chat, 'id', None)
                timestamp = getattr(chat, 'timestamp', None)
                when = {'timestamp': timestamp.timestamp()} if hasattr(timestamp, 'timestamp') else {}
                history_msgs.append({"role": "user", "content": chat.message, **when})
                # Strip suggestions from bot response for cleaner history context
                clean_response = re.sub(r'\[SUGGESTIONS:.*?\]', '', chat.response).strip()
                history_msgs.append({"role": "assistant", "content": clean_response, **when})
            history_msgs = bounded_history(history_msgs)

        owner = f'user:{request.user.pk}' if persist else 'guest'
        guest_id = data.get('context_id', '')
        guest_id = guest_id if isinstance(guest_id, str) and len(guest_id) <= 100 else ''
        thread = conversation_id if persist else guest_id
        dialogue_state = decode_dialogue_state(data.get('context_token'), owner, thread, context_anchor)
        effective_context = dialogue_state.get('query', '')
        dialogue_options = {'dialogue_state': dialogue_state} if dialogue_state.get('language') or dialogue_state.get('pending') else {}
        if effective_context:
            result = bot.process_query(user_message, history=history_msgs, context_query=effective_context, **dialogue_options)
        else:
            result = bot.process_query(user_message, history=history_msgs, **dialogue_options)
        bot_response, sources, action, action_data = result
        bot_response, suggestions, suggestions_kind = response_suggestions(
            result, user_message, history_msgs, bounded_questions(data.get('asked_questions')))
        
        # HYBRID ACCESS: SAVE Logic
        if persist:
            # Student: Save to DB
            
            # Find or Create Conversation
            if conversation is None:
                # Create new conversation if none provided
                # Use first message as title (truncated)
                title = user_message[:30] + "..." if len(user_message) > 30 else user_message
                conversation = Conversation.objects.create(user=request.user, title=title)
            
            # Update title if it's "New Chat" and this is the first real message
            if conversation.title == "New Chat":
                conversation.title = user_message[:30] + "..." if len(user_message) > 30 else user_message
                conversation.save()

            # Save Message
            chat_entry = ChatHistory.objects.create(
                user=request.user,
                conversation=conversation,
                message=user_message,
                response=bot_response
            )
            
            # Update conversation timestamp
            conversation.save()
            session = getattr(request, 'session', None)
            if session is not None:
                session['paula_conversation_id'] = conversation.id
            
            saved = True
            user_type = request.user.username
            active_conversation_id = conversation.id
            conversation_title = conversation.title
            chat_history_id = chat_entry.id
        else:
            # Guest: Do NOT Save
            saved = False
            user_type = 'guest'
            active_conversation_id = None
            conversation_title = None
            chat_history_id = None
            
        return Response({
            'response': bot_response,
            'sources': sources,
            'suggestions': suggestions,
            'suggestions_kind': suggestions_kind,
            'saved': saved,
            'user': user_type,
            'conversation_id': active_conversation_id,
            'conversation_title': conversation_title,
            'chat_history_id': chat_history_id,
            'action': action,
            'action_data': action_data,
            'answer_parts': getattr(result, 'answer_parts', []),
            'response_mode': getattr(result, 'response_mode', 'knowledge'),
            'answer_status': getattr(result, 'answer_status', 'ok' if sources or action else 'no_match'),
            'context_token': encode_context(getattr(result, 'context_query', ''), owner,
                                            active_conversation_id if persist else guest_id,
                                            chat_history_id if persist else None,
                                            language=getattr(result, 'language_preference', None),
                                            pending=getattr(result, 'pending_clarification', None)),
        })
        
    except ParseError as exc:
        return failure('invalid_json', 400, exception=exc)
    except UnsupportedMediaType as exc:
        return failure('unsupported_media_type', 415, exception=exc)
    except DatabaseError as exc:
        return failure('storage_unavailable', 503, exception=exc)
    except Exception as exc:
        return failure('request_failed', 500, exception=exc)


@api_view(['PATCH'])
def submit_feedback(request, chat_id):
    """
    Submit feedback (thumbs up/down) for a specific chat response.
    Works for both authenticated users (own messages) and allows guest feedback.
    """
    try:
        chat_entry = ChatHistory.objects.get(id=chat_id)
        
        # Security: Only the owning user can give feedback on their messages
        if request.user.is_authenticated and chat_entry.user != request.user:
            return Response({'error': 'Unauthorized'}, status=403)
        
        feedback_value = request.data.get('feedback')
        if feedback_value not in ('positive', 'negative', None):
            return Response({'error': 'Invalid feedback value'}, status=400)
        
        chat_entry.feedback = feedback_value
        chat_entry.save(update_fields=['feedback'])
        
        return Response({
            'message': 'Feedback submitted',
            'chat_id': chat_id,
            'feedback': feedback_value
        })
        
    except ChatHistory.DoesNotExist:
        return Response({'error': 'Chat entry not found'}, status=404)
    except DatabaseError as exc:
        return failure('storage_unavailable', 503, stage='feedback', exception=exc)
    except Exception as exc:
        return failure('request_failed', 500, stage='feedback', exception=exc)


# ==============================================================================
# ADMIN DASHBOARD API ENDPOINTS
# ==============================================================================

from rest_framework.permissions import IsAdminUser
from django.db.models import Count
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.core.paginator import Paginator
import json



@api_view(['GET'])
def admin_campus_pulse(request):
    """
    Campus Pulse Heatmap Data.
    Groups ChatHistory by day-of-week and hour-of-day, returns count per cell.
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)

    data = (
        ChatHistory.objects
        .annotate(
            day=ExtractWeekDay('timestamp'),
            hour=ExtractHour('timestamp')
        )
        .values('day', 'hour')
        .annotate(count=Count('id'))
        .order_by('day', 'hour')
    )
    return Response(list(data))


@api_view(['GET'])
def admin_trending_confusion(request):
    """
    Trending Confusion Bar Chart Data.
    Categorizes chat messages by keywords and returns top 10 by volume.
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)

    # Define keyword-to-category mapping
    categories = {
        'Enrollment': ['enroll', 'registration', 'register', 'admission', 'admit'],
        'Scholarship': ['scholarship', 'financial aid', 'grant', 'stipend'],
        'Leave of Absence': ['leave', 'loa', 'absence', 'withdraw'],
        'Grades': ['grade', 'gwa', 'transcript', 'mark', 'score', 'passing'],
        'Requirements': ['requirement', 'document', 'submit', 'form', 'clearance'],
        'Tuition': ['tuition', 'fee', 'payment', 'pay', 'balance', 'cashier'],
        'Schedule': ['schedule', 'class', 'time', 'calendar', 'subject'],
        'Staff': ['staff', 'faculty', 'professor', 'teacher', 'instructor', 'dean'],
        'Location': ['location', 'where', 'office', 'building', 'room', 'campus'],
        'General': [],  # fallback
    }

    messages = ChatHistory.objects.values_list('message', flat=True)
    counts = {cat: 0 for cat in categories}

    for msg in messages:
        msg_lower = msg.lower()
        matched = False
        for cat, keywords in categories.items():
            if cat == 'General':
                continue
            for kw in keywords:
                if kw in msg_lower:
                    counts[cat] += 1
                    matched = True
                    break
        if not matched:
            counts['General'] += 1

    result = [
        {'category': cat, 'count': cnt}
        for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if cnt > 0
    ][:10]

    return Response(result)


@api_view(['GET'])
def admin_metrics(request):
    """
    Enhanced summary metrics for admin dashboard cards.
    Provides comprehensive institutional metrics, feedback satisfaction, and counts.
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)

    summary = get_analytics_summary_data()
    kpis = summary['kpis']

    return Response({
        'total_enrolled': kpis['total_enrolled'],
        'at_risk': kpis['at_risk_students'],
        'unresolved_requests': kpis['open_needs'] + kpis['in_progress_needs'],
        'pending_enrollments': StudentNeed.objects.filter(
            need_type='Enrollment', status__in=['Open', 'In Progress']
        ).count(),
        'total_queries': kpis['total_queries'],
        'total_conversations': kpis['total_conversations'],
        'satisfaction_rate': kpis['satisfaction_rate'],
        'positive_feedback': kpis['positive_feedback'],
        'negative_feedback': kpis['negative_feedback'],
        'total_needs': kpis['total_needs'],
        'open_needs': kpis['open_needs'],
        'in_progress_needs': kpis['in_progress_needs'],
        'resolved_needs': kpis['resolved_needs'],
        'urgency_distribution': summary['urgency_distribution'],
        'type_distribution': summary['type_distribution'],
        'trending_topics': summary['trending_topics'],
    })


@api_view(['GET'])
def admin_reports_data(request):
    """
    Returns full institutional report dataset as JSON.
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    data = get_analytics_summary_data()
    return Response(data)


@api_view(['GET'])
def admin_reports_print(request):
    """
    Returns a ready-to-print, responsive HTML document.
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return HttpResponse('<h1>403 Unauthorized: Administrator privileges required</h1>', status=403)
    report_type = request.query_params.get('type', 'summary')
    html_content = render_print_html(report_type=report_type)
    return HttpResponse(html_content, content_type='text/html')


@api_view(['GET'])
def admin_reports_export_csv(request):
    """
    Exports institutional report data as a downloadable CSV.
    Supports ?type=summary (default), ?type=student_needs, ?type=queries.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    report_type = request.query_params.get('type', 'summary')
    csv_bytes = generate_analytics_csv(report_type=report_type)
    filename = f"paulibot_report_{report_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['GET'])
def admin_reports_export_pdf(request):
    """
    Exports institutional report data as a downloadable, branded PDF document.
    Supports ?type=summary (default).
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    report_type = request.query_params.get('type', 'summary')
    pdf_bytes = generate_analytics_pdf(report_type=report_type)
    filename = f"paulibot_report_{report_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['GET'])
def admin_student_needs(request):
    """
    Paginated list of student needs with filters.
    Query params: page, urgency, need_type, status, search
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)

    qs = StudentNeed.objects.select_related('student').all()

    # Apply filters
    urgency = request.query_params.get('urgency')
    need_type = request.query_params.get('need_type')
    need_status = request.query_params.get('status')
    search = request.query_params.get('search')

    if urgency:
        qs = qs.filter(urgency=urgency)
    if need_type:
        qs = qs.filter(need_type=need_type)
    if need_status:
        qs = qs.filter(status=need_status)
    if search:
        qs = qs.filter(
            models.Q(student__student_id__icontains=search) |
            models.Q(student__first_name__icontains=search) |
            models.Q(student__last_name__icontains=search) |
            models.Q(student__username__icontains=search)
        )

    paginator = Paginator(qs, 20)
    page_num = request.query_params.get('page', 1)
    try:
        page = paginator.page(page_num)
    except Exception:
        page = paginator.page(1)

    results = []
    for need in page:
        results.append({
            'id': need.id,
            'student_id': need.student.student_id,
            'name': f"{need.student.first_name} {need.student.last_name}".strip() or need.student.username,
            'need_type': need.need_type,
            'urgency': need.urgency,
            'status': need.status,
            'assigned_advisor': need.assigned_advisor,
            'date': need.created_at.strftime('%Y-%m-%d'),
            'description': need.description,
        })

    return Response({
        'results': results,
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'current_page': page.number,
    })


@api_view(['PATCH'])
def admin_student_need_detail(request, pk):
    """
    Update a student need record (status, assigned_advisor).
    Only accessible to superusers.
    """
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)

    try:
        need = StudentNeed.objects.get(pk=pk)
    except StudentNeed.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if 'status' in request.data:
        need.status = request.data['status']
    if 'assigned_advisor' in request.data:
        need.assigned_advisor = request.data['assigned_advisor']
    if 'urgency' in request.data:
        need.urgency = request.data['urgency']

    need.save()
    return Response({
        'message': 'Updated',
        'id': need.id,
        'status': need.status,
        'assigned_advisor': need.assigned_advisor,
    })


# ==============================================================================
# PUBLIC API
# ==============================================================================

@api_view(['GET'])
def get_announcements(request):
    """
    Fetch the latest active announcement to display on the frontend.
    Returns the single newest active announcement, or null if none exist.
    """
    latest_announcement = Announcement.objects.filter(is_active=True).order_by('-created_at').first()
    if latest_announcement:
        return Response({
            'has_announcement': True,
            'title': latest_announcement.title,
            'content': latest_announcement.content,
            'created_at': latest_announcement.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    else:
        return Response({'has_announcement': False})


@api_view(['PATCH'])
def update_profile(request):
    """
    Updates the authenticated student's nickname and/or avatar.
    Nickname is limited to 30 chars. Avatar is uploaded as multipart/form-data.
    """
    if not request.user.is_authenticated:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
    
    user = request.user
    nickname = request.data.get('nickname')
    avatar = request.FILES.get('avatar')
    
    if nickname is not None: # Allow empty nickname if user wants to clear it?
        nickname = nickname.strip()
        if len(nickname) > 30:
            return Response({'error': 'Nickname too long (max 30 chars)'}, status=status.HTTP_400_BAD_REQUEST)
        user.nickname = nickname or None # Store as None if empty
    
    if avatar:
        user.avatar = avatar
    
    user.save()
    
    return Response({
        'message': 'Profile updated successfully',
        'nickname': user.nickname or user.username,
        'avatar_url': user.avatar.url if user.avatar else None
    })

# ==============================================================================
# SMART CAMPUS NAVIGATION APIS
# ==============================================================================
from .campus_nav import get_pathfinder

@api_view(['POST'])
def calculate_campus_route(request):
    """
    Receives start and end coordinates in percentages (0-100) from React,
    converts to absolute pixels, calculates the path via A* Engine, 
    and returns a path array in percentages.
    """
    try:
        data = request.data
        if not isinstance(data, Mapping):
            return failure('invalid_request', 400, stage='navigation')
        try:
            raw = [data.get(key) for key in ('start_x', 'start_y', 'end_x', 'end_y')]
            if any(isinstance(value, bool) for value in raw):
                raise ValueError('Boolean coordinates are not positions')
            start_x_pct, start_y_pct, end_x_pct, end_y_pct = coordinates = [float(value) for value in raw]
            if any(not math.isfinite(value) or not 0 <= value <= 100 for value in coordinates):
                raise ValueError('Coordinates must be finite percentages')
        except (TypeError, ValueError):
            return failure('invalid_coordinates', 400, stage='navigation')
        
        pathfinder = get_pathfinder()
        
        orig_w, orig_h = pathfinder.orig_size
        
        # Convert % to absolute pixels on the original 4500x2800 image
        start_x = int((start_x_pct / 100.0) * orig_w)
        start_y = int((start_y_pct / 100.0) * orig_h)
        end_x = int((end_x_pct / 100.0) * orig_w)
        end_y = int((end_y_pct / 100.0) * orig_h)
        
        # Run Pathfinding
        route_pixels = pathfinder.calculate_path(start_x, start_y, end_x, end_y)
        
        if not route_pixels:
            return Response({'error': 'Path blocked or not found'}, status=404)
            
        # Convert pixels back to %
        route_pct = [
            {'x': (px / orig_w) * 100.0, 'y': (py / orig_h) * 100.0}
            for (px, py) in route_pixels
        ]
        
        # We can also calculate distance. (e.g. number of pixels walked * scale factor)
        # Just passing back the raw array length as a placeholder for distance
        distance_estimate = len(route_pixels) * pathfinder.scale
        
        return Response({
            'status': 'success',
            'path': route_pct,
            'distance_pixels': distance_estimate
        })
        
    except ParseError as exc:
        return failure('invalid_json', 400, stage='navigation', exception=exc)
    except UnsupportedMediaType as exc:
        return failure('unsupported_media_type', 415, stage='navigation', exception=exc)
    except Exception as exc:
        return failure('navigation_unavailable', 503, stage='navigation', exception=exc)
