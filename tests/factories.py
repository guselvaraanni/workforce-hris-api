import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from employees.models import Department, EmployeeProfile, LeaveRequest
from datetime import timedelta
from django.utils import timezone

CustomUser = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = CustomUser
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default _create to use create_user"""
        password = kwargs.pop('password', 'testpass123')
        manager = model_class(*args, **kwargs)
        manager.set_password(password)
        manager.save()
        return manager


class DepartmentFactory(DjangoModelFactory):
    """Factory for creating test departments"""
    class Meta:
        model = Department
    
    name = factory.Sequence(lambda n: f'Department {n}')
    description = factory.Faker('text')
    budget = factory.Faker('pydecimal', left_digits=5, right_digits=2, positive=True)
    is_active = True


class EmployeeProfileFactory(DjangoModelFactory):
    """Factory for creating test employee profiles"""
    class Meta:
        model = EmployeeProfile
    
    user = factory.SubFactory(UserFactory)
    employee_id = factory.Sequence(lambda n: f'EMP{n:05d}')
    department = factory.SubFactory(DepartmentFactory)
    date_of_birth = factory.Faker('date_of_birth', minimum_age=20, maximum_age=65)
    gender = factory.Faker('random_element', elements=['M', 'F', 'O'])
    address = factory.Faker('address')
    city = factory.Faker('city')
    country = factory.Faker('country')
    postal_code = factory.Faker('postcode')
    employment_status = 'active'
    employment_type = 'full_time'
    salary = factory.Faker('pydecimal', left_digits=5, right_digits=2, positive=True)
    bonus = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)


class LeaveRequestFactory(DjangoModelFactory):
    """Factory for creating test leave requests"""
    class Meta:
        model = LeaveRequest
    
    employee = factory.SubFactory(EmployeeProfileFactory)
    start_date = factory.Faker('date_object')
    leave_type = 'annual'
    reason = factory.Faker('text')
    status = 'pending'
    
    @factory.lazy_attribute
    def end_date(self):
        return self.start_date + timedelta(days=5)
