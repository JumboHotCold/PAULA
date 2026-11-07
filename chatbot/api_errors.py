"""Safe public errors with payload-free, request-correlated diagnostics."""
from rest_framework.response import Response
from .performance import diagnostic_error

MESSAGES = {
    'invalid_json': 'Please send a valid JSON request.',
    'unsupported_media_type': 'Please send JSON or form data.',
    'invalid_request': 'Please send a request containing named fields.',
    'invalid_message': 'Please enter a message between 1 and 2,000 characters.',
    'invalid_conversation': 'Please select a valid conversation or start a new chat.',
    'invalid_coordinates': 'Please choose valid starting and destination points on the map.',
    'storage_unavailable': 'PAULA cannot access the information needed right now. Please try again shortly.',
    'navigation_unavailable': 'Campus directions are temporarily unavailable. Please try again shortly.',
    'request_failed': 'PAULA could not complete this request. Please try again shortly.',
}


def failure(code, status, *, stage='chat', exception=None):
    request_id = diagnostic_error(stage, code, exception)
    return Response({'error': MESSAGES[code], 'error_code': code, 'request_id': request_id}, status=status)
