from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Occupation, Level, Module, Paper, OccupationLevel

@require_GET
def api_informal_modules_papers(request):
    """
    Given occupation_id and level_id, return modules and their papers for informal enrollment.
    Response: { modules: [ {id, name, papers: [{id, name}]} ] }
    """
    occupation_id = request.GET.get('occupation_id')
    level_id = request.GET.get('level_id')
    modules_qs = Module.objects.filter(occupation_id=occupation_id, level_id=level_id)
    modules = []
    for mod in modules_qs:
        papers = list(Paper.objects.filter(module=mod).values('id', 'name'))
        modules.append({
            'id': mod.id,
            'name': mod.name,
            'papers': papers
        })
    return JsonResponse({'modules': modules})
