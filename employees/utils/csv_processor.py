import csv
import logging
import threading
from io import StringIO
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from ..models import CustomUser, Department, EmployeeProfile, BulkUploadJob

logger = logging.getLogger(__name__)


def process_csv_file(job_id):
    """
    Process CSV file and bulk create employee records.
    Runs in a separate thread to avoid blocking the API.
    
    Args:
        job_id: ID of the BulkUploadJob
    """
    try:
        job = BulkUploadJob.objects.get(id=job_id)
        job.status = 'processing'
        job.started_at = timezone.now()
        job.thread_id = threading.current_thread().name
        job.save()
        
        logger.info(f"Starting CSV processing for job {job_id}")
        
        # Read CSV file
        csv_content = job.csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_content))
        
        # Validate headers
        required_headers = ['email', 'first_name', 'last_name', 'employee_id', 'salary', 'department']
        if not all(header in csv_reader.fieldnames for header in required_headers):
            job.status = 'failed'
            job.error_log = [f'Missing required headers: {required_headers}']
            job.completed_at = timezone.now()
            job.save()
            logger.error(f"Invalid CSV headers for job {job_id}")
            return
        
        rows = list(csv_reader)
        job.total_records = len(rows)
        job.save()
        
        # Process each row
        errors = []
        
        for idx, row in enumerate(rows):
            try:
                with transaction.atomic():
                    # Validate row data
                    email = row.get('email', '').strip()
                    first_name = row.get('first_name', '').strip()
                    last_name = row.get('last_name', '').strip()
                    employee_id = row.get('employee_id', '').strip()
                    salary = row.get('salary', '').strip()
                    department_name = row.get('department', '').strip()
                    
                    # Validate required fields
                    if not all([email, first_name, last_name, employee_id, salary]):
                        raise ValueError('Missing required fields')
                    
                    # Validate salary is a number
                    try:
                        salary = Decimal(salary)
                        if salary < 0:
                            raise ValueError('Salary cannot be negative')
                    except:
                        raise ValueError(f'Invalid salary value: {salary}')
                    
                    # Check if user already exists
                    if CustomUser.objects.filter(email=email).exists():
                        raise ValueError(f'User with email {email} already exists')
                    
                    # Check if employee_id already exists
                    if EmployeeProfile.objects.filter(employee_id=employee_id).exists():
                        raise ValueError(f'Employee ID {employee_id} already exists')
                    
                    # Get or create department
                    department, _ = Department.objects.get_or_create(
                        name=department_name,
                        defaults={'description': f'Auto-created department: {department_name}'}
                    )
                    
                    # Create user
                    user = CustomUser.objects.create_user(
                        email=email,
                        username=email,
                        first_name=first_name,
                        last_name=last_name,
                        password=CustomUser.objects.make_random_password()  # Random password
                    )
                    
                    # Create employee profile
                    EmployeeProfile.objects.create(
                        user=user,
                        employee_id=employee_id,
                        salary=salary,
                        department=department,
                        employment_status='active',
                        employment_type=row.get('employment_type', 'full_time'),
                        date_of_birth=parse_date(row.get('date_of_birth')),
                        gender=row.get('gender', 'O'),
                        address=row.get('address', ''),
                        city=row.get('city', ''),
                        country=row.get('country', ''),
                        postal_code=row.get('postal_code', ''),
                        bio=row.get('bio', ''),
                        skills=row.get('skills', '')
                    )
                    
                    job.successful_records += 1
                    job.processed_records += 1
                    
            except Exception as e:
                error_msg = f"Row {idx + 1}: {str(e)}"
                errors.append(error_msg)
                job.failed_records += 1
                job.processed_records += 1
                logger.warning(f"Error processing row {idx + 1} in job {job_id}: {str(e)}")
            
            # Update job progress
            if (idx + 1) % 10 == 0:
                job.save()
        
        # Mark job as completed
        job.status = 'completed'
        job.error_log = errors
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(
            f"Completed CSV processing for job {job_id}: "
            f"{job.successful_records} successful, {job.failed_records} failed"
        )
    
    except BulkUploadJob.DoesNotExist:
        logger.error(f"Bulk upload job {job_id} not found")
    
    except Exception as e:
        logger.error(f"Error processing CSV for job {job_id}: {str(e)}", exc_info=True)
        try:
            job = BulkUploadJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_log = [f'Processing error: {str(e)}']
            job.completed_at = timezone.now()
            job.save()
        except:
            pass


def parse_date(date_str):
    """
    Parse date string in common formats.
    """
    if not date_str:
        return None
    
    formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except:
            continue
    
    return None
