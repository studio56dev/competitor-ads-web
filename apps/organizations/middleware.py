"""Attaches the current user's primary organization to each request."""


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_organization = None
        request.user_membership = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            membership = (
                user.memberships.select_related("organization")
                .order_by("joined_at")
                .first()
            )
            if membership:
                request.user_membership = membership
                request.user_organization = membership.organization
        return self.get_response(request)
