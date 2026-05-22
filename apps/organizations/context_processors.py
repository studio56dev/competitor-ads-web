def organization(request):
    return {
        "user_organization": getattr(request, "user_organization", None),
        "user_membership": getattr(request, "user_membership", None),
    }
