from django.conf import settings

def env_flags(request):
    """Expose environment flags to all templates.
    - IS_STAGING: bool indicating training/staging site
    - SITE_NAME: customizable site label
    """
    return {
        'IS_STAGING': getattr(settings, 'IS_STAGING', False),
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'EMIS Dashboard'),
    }
