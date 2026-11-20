from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Uniform error envelope: {"error": {"status", "detail"|"fields"}}."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"}:
        body = {"status": response.status_code, "detail": str(data["detail"])}
    else:
        body = {"status": response.status_code, "detail": "Validation failed." if response.status_code == 400 else "Request failed.", "fields": data}
    response.data = {"error": body}
    return response
