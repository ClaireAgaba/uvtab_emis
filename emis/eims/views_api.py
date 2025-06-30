from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from .models import Occupation, Level, Module, Paper, OccupationLevel

@login_required
@require_POST
def api_add_level(request, occupation_id):
    name = request.POST.get('level_name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': 'Level name is required.'})
    occupation = Occupation.objects.get(pk=occupation_id)
    occ_code = occupation.code.strip() if occupation.code else ''
    # If name does not already end with the occupation code, append it
    if occ_code and not name.endswith(occ_code):
        name = f"{name} {occ_code}"
    if Level.objects.filter(name=name, occupation=occupation).exists():
        return JsonResponse({'success': False, 'error': f"Level '{name}' already exists for this occupation."})
    level = Level.objects.create(name=name, occupation=occupation)
    # Optionally, create OccupationLevel as well
    OccupationLevel.objects.create(occupation=occupation, level=level, structure_type='modules')
    # Build selected_levels: all OccupationLevel assignments for this occupation
    occupation_levels = OccupationLevel.objects.filter(occupation=occupation)
    selected_levels = {str(ol.level.id): ol.structure_type for ol in occupation_levels}
    levels = list(Level.objects.filter(occupation=occupation).values('id', 'name'))
    return JsonResponse({'success': True, 'levels': levels, 'selected_levels': selected_levels, 'added': {'id': level.id, 'name': level.name}})

@login_required
@require_POST
def api_remove_level(request, occupation_id):
    level_id = request.POST.get('level_id')
    occupation = Occupation.objects.get(pk=occupation_id)
    try:
        level = Level.objects.get(pk=level_id, occupation=occupation)
        # Only allow removal if not used elsewhere (add logic as needed)
        level.delete()
        OccupationLevel.objects.filter(occupation=occupation, level=level).delete()
        # Build selected_levels: all OccupationLevel assignments for this occupation
        occupation_levels = OccupationLevel.objects.filter(occupation=occupation)
        selected_levels = {str(ol.level.id): ol.structure_type for ol in occupation_levels}
        levels = list(Level.objects.filter(occupation=occupation).values('id', 'name'))
        return JsonResponse({'success': True, 'levels': levels, 'selected_levels': selected_levels, 'removed': level_id})
    except Level.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Level not found.'})

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
