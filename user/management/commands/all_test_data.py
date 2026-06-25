from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from user.models import UserProfile 

TEST_ACCOUNTS = [
    {"username": "23-22-022", "first_name": "Juan", "last_name": "Dela Cruz", "password": "testpass123", "is_staff": False, "department": "College of Computing Studies", "email": "jdlc@gmail.com", "phone": "09123456789"},
    {"username": "23-22-055", "first_name": "Marie", "last_name": "Bella", "password": "testpass123", "is_staff": False, "department": "College of Education", "email": "mbl@gmail.com", "phone": "09123456789"},
    {"username": "19-02-001", "first_name": "Head", "last_name": "Admin", "password": "admin001", "is_staff": True, "department": "Maintenance and Engineering Division", "email": "admin@gmail.com", "phone": "09123456789"},
]

class Command(BaseCommand):
    help = "Shared accounts for test data"

    def handle(self, *args, **kwargs):
        for account in TEST_ACCOUNTS:
            user, created = User.objects.get_or_create(
                username = account["username"],
                defaults = {
                    "first_name": account["first_name"],
                    "last_name": account["last_name"],
                    "is_staff": account["is_staff"],
                    "email": account["email"],
                },
            )

            if created:
                user.set_password(account["password"])
                user.save()
                UserProfile.objects.create(
                    user=user,
                    role="staff" if account["is_staff"] else "student",
                    department=account["department"],
                    phone=account["phone"],
                )
                self.stdout.write(self.style.SUCCESS(f"Created {account['username']} ({account['first_name']} {account['last_name']})"))
            else:
                self.stdout.write((f"{account['username']} already exist"))

        self.stdout.write(self.style.SUCCESS("Done"))
