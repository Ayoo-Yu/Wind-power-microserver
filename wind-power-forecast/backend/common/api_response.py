def success(data=None, message="ok", code=0, request_id=None):
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id,
    }


def error(message, code, details=None, request_id=None):
    return {
        "code": code,
        "message": message,
        "details": details,
        "request_id": request_id,
    }

