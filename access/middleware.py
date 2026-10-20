from functools import wraps
from operator_auth import current_operator as get_current_user, require_operator


def require_auth(request):
    return require_operator(request)


def get_user_tier(request):
    return "admin" if get_current_user(request) else None


def is_admin(request):
    return get_current_user(request) is not None


def require_admin(func):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        require_operator(request)
        return await func(request, *args, **kwargs)

    return wrapper
