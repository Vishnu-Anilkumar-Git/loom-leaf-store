"""Template tags used by dashboard templates (query strings, pagination)."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Current query string with the given parameters replaced.

    Passing an empty/None value removes the parameter, so ``{% qs_replace page=1 %}``
    keeps filters such as ``q`` and ``status`` while resetting pagination.
    """
    request = context.get("request")
    params = request.GET.copy() if request is not None else template.Context()
    for key, value in kwargs.items():
        if value is None or value == "":
            if hasattr(params, "pop"):
                params.pop(key, None)
        else:
            params[key] = str(value)
    encoded = params.urlencode() if hasattr(params, "urlencode") else ""
    return f"?{encoded}" if encoded else "?"


@register.simple_tag
def page_window(page, radius=2):
    """Page numbers around the current page; ``None`` marks an ellipsis gap."""
    if page is None:
        return []
    current = page.number
    total = page.paginator.num_pages
    wanted = set()
    for number in range(current - radius, current + radius + 1):
        if 1 <= number <= total:
            wanted.add(number)
    wanted.update({1, total})
    ordered = sorted(wanted)
    window = []
    previous = None
    for number in ordered:
        if previous is not None and number - previous > 1:
            window.append(None)
        window.append(number)
        previous = number
    return window
