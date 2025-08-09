from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
from .models import Candidate
import os
import mimetypes

@login_required
@require_http_methods(["GET"])
def serve_candidate_document(request, candidate_id, document_type):
    """
    Securely serve candidate documents with proper authentication and authorization.
    Only authenticated users can access documents.
    """
    # Get the candidate object
    candidate = get_object_or_404(Candidate, id=candidate_id)
    
    # Determine which document to serve
    if document_type == 'identification':
        document_field = candidate.identification_document
    elif document_type == 'qualification':
        document_field = candidate.qualification_document
    else:
        raise Http404("Invalid document type")
    
    # Check if document exists
    if not document_field:
        raise Http404("Document not found")
    
    # Get the file path
    file_path = document_field.path
    
    # Check if file exists on filesystem
    if not os.path.exists(file_path):
        raise Http404("File not found on server")
    
    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'
    
    # Read and serve the file
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        response = HttpResponse(file_data, content_type=content_type)
        
        # Set appropriate headers
        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Content-Length'] = len(file_data)
        
        return response
        
    except IOError:
        raise Http404("Error reading file")
