from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles: list):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                role_display = request.user.profile.get_role_display()
                if role_display in allowed_roles:
                    return view_func(request, *args, **kwargs)
            except:
                pass
            return redirect('not_access')
        return wrapper
    return decorator