def get_user_repr(user):
    """Turn user object into dict with required properties"""
    if user.is_anonymous:
        return {'key': str(user), 'custom': {'organization': None}}
    user_data = {'email': user.email}
    user_data['key'] = user_data['email']
    if user.active_organization is not None:
        created_by_email = None
        try:
            if user.active_organization.created_by_id:
                created_by_email = user.active_organization.created_by.email
        except Exception:
            pass
        user_data['custom'] = {'organization': created_by_email}
    else:
        user_data['custom'] = {'organization': None}
    return user_data