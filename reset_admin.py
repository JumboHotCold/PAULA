import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paulibot.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("--- Existing Users ---")
users = User.objects.all()
if not users.exists():
    print("No users found in database.")
else:
    for u in users:
        print(f"Username: {u.username}, Email: {u.email}, Is Superuser: {u.is_superuser}, Is Active: {u.is_active}")

# Create or update default admin user
admin_username = "admin"
admin_email = "admin@example.com"
admin_password = "adminpassword123"

admin_user, created = User.objects.get_or_create(username=admin_username, defaults={'email': admin_email})
admin_user.set_password(admin_password)
admin_user.is_superuser = True
admin_user.is_staff = True
admin_user.is_active = True
admin_user.save()

if created:
    print(f"\nCreated new Superuser: Username='{admin_username}', Password='{admin_password}'")
else:
    print(f"\nReset existing Superuser password: Username='{admin_username}', Password='{admin_password}'")
