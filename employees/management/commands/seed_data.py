from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import CustomUser, Department, EmployeeProfile
from faker import Faker
from decimal import Decimal
import random

fake = Faker()


class Command(BaseCommand):
    help = 'Seed the database with dummy employee data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--employees',
            type=int,
            default=50,
            help='Number of employees to create'
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        num_employees = options['employees']
        
        self.stdout.write(self.style.SUCCESS('Starting database seeding...'))
        
        # Create departments
        self.stdout.write('Creating departments...')
        departments = []
        dept_names = ['Engineering', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations']
        
        for dept_name in dept_names:
            dept, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={
                    'description': f'{dept_name} Department',
                    'budget': Decimal(str(random.uniform(100000, 500000)))
                }
            )
            departments.append(dept)
            if created:
                self.stdout.write(f'  Created department: {dept_name}')
        
        # Create HR Admin
        self.stdout.write('Creating HR Admin user...')
        hr_admin_user, created = CustomUser.objects.get_or_create(
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
            hr_admin_user.set_password('Hr@Admin123')
            hr_admin_user.save()
            self.stdout.write('  Created HR Admin user')
        
        # Create employees
        self.stdout.write(f'Creating {num_employees} employees...')
        
        for i in range(num_employees):
            email = f'employee{i+1}@example.com'
            
            # Check if user already exists
            if CustomUser.objects.filter(email=email).exists():
                continue
            
            # Create user
            user = CustomUser.objects.create_user(
                email=email,
                username=f'user{i+1}',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                password='TestPass123!',
                phone_number=fake.phone_number()[:15],
                is_manager=random.choice([True, False]) if i % 10 == 0 else False,
                is_active=True
            )
            
            # Create employee profile
            department = random.choice(departments)
            
            EmployeeProfile.objects.create(
                user=user,
                employee_id=f'EMP{i+1:05d}',
                department=department,
                date_of_birth=fake.date_of_birth(minimum_age=22, maximum_age=65),
                gender=random.choice(['M', 'F', 'O']),
                address=fake.address(),
                city=fake.city(),
                country=fake.country(),
                postal_code=fake.postcode(),
                employment_status='active',
                employment_type=random.choice(['full_time', 'part_time', 'contract']),
                salary=Decimal(str(random.uniform(40000, 120000))),
                bonus=Decimal(str(random.uniform(0, 20000))),
                bio=fake.text(max_nb_chars=200),
                skills=';'.join(fake.words(nb=5))
            )
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f'  Created {i + 1} employees...')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {num_employees} employees!'))
        self.stdout.write(self.style.SUCCESS('Database seeding completed!'))
        self.stdout.write(self.style.WARNING('\nDefault credentials:'))
        self.stdout.write(f'  Email: hr@example.com')
        self.stdout.write(f'  Password: Hr@Admin123')
