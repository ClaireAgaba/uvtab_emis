from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Sector, Occupation, Candidate, AssessmentSeries
from .forms import SectorForm

@login_required
def sector_list(request):
    """List all sectors with search and pagination"""
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '25')
    
    # Get all sectors
    sectors = Sector.objects.all().order_by('name')
    
    # Apply search filter
    if search_query:
        sectors = sectors.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Pagination
    try:
        per_page = int(per_page)
        if per_page not in [25, 50, 100]:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25
    
    paginator = Paginator(sectors, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'sectors': page_obj,  # Template expects 'sectors'
        'page_obj': page_obj,
        'search_query': search_query,
        'per_page': per_page,
        'total_count': paginator.count,
        'items_per_page': per_page,  # Template expects 'items_per_page'
        'filters': {'search': search_query},  # Template expects 'filters'
    }
    
    return render(request, 'sectors/list.html', context)

@login_required
def sector_create(request):
    """Create a new sector"""
    if request.method == 'POST':
        form = SectorForm(request.POST)
        if form.is_valid():
            sector = form.save(commit=False)
            sector.created_by = request.user
            sector.updated_by = request.user
            sector.save()
            messages.success(request, f'Sector "{sector.name}" has been created successfully.')
            return redirect('sector_list')
    else:
        form = SectorForm()
    
    context = {
        'form': form,
        'title': 'Create New Sector',
    }
    
    return render(request, 'sectors/create.html', context)

@login_required
def sector_detail(request, pk):
    """View sector details with real statistics"""
    sector = get_object_or_404(Sector, pk=pk)
    
    # Calculate statistics
    # Related Occupations: Count of occupations in this sector
    related_occupations_count = Occupation.objects.filter(sector=sector).count()
    
    # Active Assessments: Count of current/active assessment series
    # (assuming active means current series or recent series)
    active_assessments_count = AssessmentSeries.objects.filter(is_current=True).count()
    
    # Total Candidates: Count of candidates enrolled in occupations of this sector
    total_candidates_count = Candidate.objects.filter(
        occupation__sector=sector,
        status='Active'  # Only count active candidates
    ).count()
    
    # Get list of occupations in this sector for additional context
    sector_occupations = Occupation.objects.filter(sector=sector).select_related('category')
    
    context = {
        'sector': sector,
        'related_occupations_count': related_occupations_count,
        'active_assessments_count': active_assessments_count,
        'total_candidates_count': total_candidates_count,
        'sector_occupations': sector_occupations,
    }
    
    return render(request, 'sectors/detail.html', context)

@login_required
def sector_edit(request, pk):
    """Edit an existing sector"""
    sector = get_object_or_404(Sector, pk=pk)
    
    if request.method == 'POST':
        form = SectorForm(request.POST, instance=sector)
        if form.is_valid():
            sector = form.save(commit=False)
            sector.updated_by = request.user
            sector.save()
            messages.success(request, f'Sector "{sector.name}" has been updated successfully.')
            return redirect('sector_detail', pk=sector.pk)
    else:
        form = SectorForm(instance=sector)
    
    context = {
        'form': form,
        'sector': sector,
        'title': f'Edit Sector: {sector.name}',
    }
    
    return render(request, 'sectors/edit.html', context)

@login_required
def sector_delete(request, pk):
    """Delete a sector"""
    sector = get_object_or_404(Sector, pk=pk)
    
    if request.method == 'POST':
        sector_name = sector.name
        sector.delete()
        messages.success(request, f'Sector "{sector_name}" has been deleted successfully.')
        return redirect('sector_list')
    
    context = {
        'sector': sector,
    }
    
    return render(request, 'sectors/delete_confirm.html', context)
