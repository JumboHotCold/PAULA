"""Read-only dependency health; index warnings do not disable exact FAQ paths."""
from django.db import DatabaseError, connection
from django.db.models import Count, Q
from .models import FAQ, Location, StaffMember, WebResource
from .performance import diagnostic_error
from .readiness import readiness_state


def knowledge_health():
    if connection.vendor != 'postgresql':
        return {'database_ready': False, 'knowledge_available': False, 'index_complete': False}
    try:
        counts = {model.__name__: model.objects.aggregate(total=Count('pk'), missing=Count('pk', filter=Q(embedding__isnull=True)))
                  for model in (FAQ, Location, StaffMember, WebResource)}
        total = sum(row['total'] for row in counts.values())
        return {'database_ready': True, 'knowledge_available': total > 0,
                'index_complete': total > 0 and all(row['missing'] == 0 for row in counts.values()), 'knowledge': counts}
    except DatabaseError as exc:
        diagnostic_error('readiness', 'storage_unavailable', exc)
        return {'database_ready': False, 'knowledge_available': False, 'index_complete': False}


def service_readiness():
    state = readiness_state()
    health = knowledge_health()
    return {**state, **health, 'ready': state['ready'] and health['database_ready'] and health['knowledge_available']}
