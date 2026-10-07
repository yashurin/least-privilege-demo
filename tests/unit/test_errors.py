from fastapi import status

from app.errors import bad_request, forbidden, invalid_credentials, not_found, unauthorized


def test_unauthorized_challenges_with_bearer():
    error = unauthorized()
    assert error.status_code == status.HTTP_401_UNAUTHORIZED
    assert error.detail == "Not authenticated"
    assert error.headers == {"WWW-Authenticate": "Bearer"}


def test_invalid_credentials_hides_which_check_failed():
    error = invalid_credentials()
    assert error.status_code == status.HTTP_401_UNAUTHORIZED
    assert error.detail == "Invalid credentials"
    assert error.headers is None


def test_forbidden_and_not_found_use_stable_bodies():
    assert forbidden().status_code == status.HTTP_403_FORBIDDEN
    assert forbidden().detail == "Forbidden"
    assert not_found().status_code == status.HTTP_404_NOT_FOUND
    assert not_found().detail == "Not found"


def test_bad_request_keeps_the_caller_message():
    error = bad_request("Unknown catalog item")
    assert error.status_code == status.HTTP_400_BAD_REQUEST
    assert error.detail == "Unknown catalog item"
