from operator_auth import require_operator


def require_admin_access(request):
    return require_operator(request)


def require_setup_access(request):
    return require_operator(request)
