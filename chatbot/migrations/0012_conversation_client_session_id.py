from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('chatbot', '0011_faq_source_office_faq_source_type')]
    operations = [
        migrations.AddField(model_name='conversation', name='client_session_id',
                            field=models.UUIDField(blank=True, editable=False, null=True)),
        migrations.AddConstraint(model_name='conversation', constraint=models.UniqueConstraint(
            fields=('user', 'client_session_id'), name='unique_user_chat_session')),
    ]
