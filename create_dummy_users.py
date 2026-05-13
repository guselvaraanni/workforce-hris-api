#!/usr/bin/env python
"""
Create dummy users for testing the login functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from employees.models import CustomUser

def create_dummy_users():
    print("Creating dummy users for testing...")
    
    # Create HR Admin user
    hr_user, created = CustomUser.objects.get_or_create(
        email='hr@example.com',
        defaults={
            'username': 'hr_admin',
            'first_name': 'HR',
            'last_name': 'Admin',
            'is_hr_admin': True,
            'is_active': True
        }
    )
    
    if created:
        hr_user.set_password('Hr@Admin123')
        hr_user.save()
        print("✅ Created HR Admin user: hr@example.com / Hr@Admin123")
    else:
        # Update password if user exists
        hr_user.set_password('Hr@Admin123')
        hr_user.save()
        print("✅ Updated HR Admin user: hr@example.com / Hr@Admin123")
    
    # Create Manager user
    manager_user, created = CustomUser.objects.get_or_create(
        email='employee1@example.com',
        defaults={
            'username': 'manager_user',
            'first_name': 'Manager',
            'last_name': 'User',
            'is_manager': True,
            'is_active': True
        }
    )
    
    if created:
        manager_user.set_password('TestPass123!')
        manager_user.save()
        print("✅ Created Manager user: employee1@example.com / TestPass123!")
    else:
        # Update password if user exists
        manager_user.set_password('TestPass123!')
        manager_user.save()
        print("✅ Updated Manager user: employee1@example.com / TestPass123!")
    
    print("\n✅ All dummy users created successfully!")
    print("\nYou can now login with these credentials:")
    print("━" * 50)
    print("HR Admin:")
    print(f"  Email: hr@example.com")
    print(f"  Password: Hr@Admin123")
    print("━" * 50)
    print("Manager:")
    print(f"  Email: employee1@example.com")
    print(f"  Password: TestPass123!")
    print("━" * 50)

if __name__ == '__main__':
    create_dummy_users()
