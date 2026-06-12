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
