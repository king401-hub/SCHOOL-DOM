from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def attr(obj, name):
    value = obj
    for part in name.split("."):
        if value is None:
            return ""
        value = getattr(value, part, "")
        if callable(value):
            value = value()
    return value


@register.filter
def naira(value):
    """₦ + thousands separator - same convention as
    superadmin_dashboard.services._money, for templates (like payments.html)
    that work with raw Decimal totals rather than pre-formatted strings."""
    try:
        return f"₦{Decimal(value):,.0f}"
    except Exception:
        return "₦0"
