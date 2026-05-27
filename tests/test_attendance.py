import pytest
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import AttendanceRecord
from employees.utils.attendance_service import check_in, check_out, build_today_summary
from tests.factories import UserFactory


def _user_with_profile():
    user = UserFactory()
    return user.profile


@pytest.mark.django_db
class TestAttendanceService:
    def test_check_in_and_check_out(self):
        profile = _user_with_profile()
        user = profile.user
        record, err = check_in(user)
        assert err is None
        assert record.check_in is not None

        record2, err2 = check_in(user)
        assert record2 is None
        assert 'already checked in' in err2['error'].lower()

        record3, err3 = check_out(user)
        assert err3 is None
        assert record3.check_out is not None

        record4, err4 = check_out(user)
        assert record4 is None
        assert 'already checked out' in err4['error'].lower()

    def test_today_summary(self):
        profile = _user_with_profile()
        summary = build_today_summary(profile)
        assert summary['status'] in ('not_started', 'checked_in', 'completed', 'on_leave', 'absent')


@pytest.mark.django_db
class TestAttendanceAPI:
    def test_check_in_endpoint(self):
        profile = _user_with_profile()
        client = APIClient()
        client.force_authenticate(user=profile.user)
        response = client.post('/api/v1/attendance/check_in/')
        assert response.status_code == status.HTTP_200_OK
        assert AttendanceRecord.objects.filter(employee=profile).exists()
