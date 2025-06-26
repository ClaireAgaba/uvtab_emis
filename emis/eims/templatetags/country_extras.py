from django import template
from django_countries import countries

register = template.Library()

@register.filter
def country_name(value):
    """
    Given a country code or name, always return the full country name.
    """
    if not value:
        return ''
    value = str(value)
    code_to_name = dict(countries)
    name_to_name = {name.lower(): name for code, name in countries}
    if len(value) == 2 and value.isupper():
        return code_to_name.get(value, value)
    # If it's already a name, normalize
    return name_to_name.get(value.lower(), value)
