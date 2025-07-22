from django import template

register = template.Library()

@register.filter
def has_ctr(results):
    """Check if any result in the list has a comment of 'CTR'"""
    if not results:
        return False
    
    # Check for CTR in comments
    for r in results:
        if isinstance(r, dict):
            comment = r.get('comment', None)
        else:
            comment = getattr(r, 'comment', None)
        
        if comment == 'CTR':
            return True
    
    return False
