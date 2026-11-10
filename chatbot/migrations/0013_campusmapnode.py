import uuid
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [('chatbot', '0012_conversation_client_session_id')]
    operations = [
        migrations.CreateModel(
            name='CampusMapNode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('x', models.FloatField()),
                ('y', models.FloatField()),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddConstraint('campusmapnode', models.UniqueConstraint(Lower('name'), name='unique_campus_node_name')),
        migrations.AddConstraint('campusmapnode', models.CheckConstraint(
            check=models.Q(x__gte=0, x__lte=100, y__gte=0, y__lte=100),
            name='campus_node_coordinates_in_bounds')),
    ]
