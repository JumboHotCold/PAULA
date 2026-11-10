"""Public campus pins with session-authenticated administrator creation."""
import math
import unicodedata
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .intents import DESTINATIONS
from .models import CampusMapNode


class MapNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampusMapNode
        fields = ['name', 'x', 'y']

    def validate_name(self, value):
        value = ' '.join(value.split())
        if not value or any(unicodedata.category(char).startswith('C') for char in value):
            raise serializers.ValidationError('Enter a valid node name.')
        builtins = {label.casefold() for label, _ in DESTINATIONS.values()}
        builtins.update(alias.casefold() for _, aliases in DESTINATIONS.values() for alias in aliases)
        if value.casefold() in builtins or CampusMapNode.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError('A location with this name already exists.')
        return value

    def validate(self, attrs):
        for key in ('x', 'y'):
            if isinstance(self.initial_data.get(key), bool) or not math.isfinite(attrs[key]) or not 0 <= attrs[key] <= 100:
                raise serializers.ValidationError({key: 'Choose a point inside the map.'})
        return attrs


def node_data(node):
    return {'id': f'custom_{node.id}', 'name': node.name, 'x': node.x, 'y': node.y,
            'type': 'office', 'aliases': [node.name.lower()]}


@api_view(['GET', 'POST'])
def campus_map_nodes(request):
    if request.method == 'GET':
        return Response({'nodes': [node_data(node) for node in CampusMapNode.objects.all()]})
    if not request.user.is_authenticated or not request.user.is_superuser:
        return Response({'error': 'Administrator access is required.'}, status=403)
    serializer = MapNodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            node = serializer.save()
    except IntegrityError:
        return Response({'name': ['A location with this name already exists.']}, status=400)
    return Response(node_data(node), status=201)
