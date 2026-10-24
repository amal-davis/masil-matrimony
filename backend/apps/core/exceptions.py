import logging

from django.http import JsonResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """
    Use DRF's handling for expected API errors. For unexpected exceptions,
    log the full traceback and return a generic JSON 500 so internal details
    are never sent to clients.
    """
    response = exception_handler(exc, context)
    if response is not None:
        # A permission error with its own code (e.g. "email_not_verified") says which, so clients can act on it.
        if isinstance(exc, PermissionDenied) and isinstance(response.data, dict):
            code = exc.get_codes()
            if isinstance(code, str) and code != PermissionDenied.default_code:
                response.data["code"] = code
        return response

    view = context.get("view")
    logger.exception(
        "Unhandled API exception in %s", view.__class__.__name__ if view else "unknown view"
    )
    return JsonResponse(
        {"detail": "An unexpected error occurred. Please try again later."},
        status=500,
    )


def json_not_found(request, exception=None):
    return JsonResponse({"detail": "Not found."}, status=404)


def json_server_error(request):
    return JsonResponse(
        {"detail": "An unexpected error occurred. Please try again later."},
        status=500,
    )
