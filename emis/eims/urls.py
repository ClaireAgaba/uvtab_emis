from django.urls import path
from . import views
from . import views_api
from . import views_fees
from . import sector_views
from . import document_views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('candidates/import-dual/', views.candidate_import_dual, name='candidate_import_dual'),
    path('candidates/bulk-action/', views.bulk_candidate_action, name='bulk_candidate_action'),
    path('candidates/bulk-modules/', views.bulk_candidate_modules, name='bulk_candidate_modules'),
    path('candidates/export/', views.export_candidates, name='export_candidates'),
    #path('create/', views.eims_create, name='eims_create'),
    # add more views later

    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('admin/fix-photos/', views.fix_all_photos, name='fix_all_photos'),
    path('assessment-centers/', views.assessment_center_list, name='assessment_center_list'),
    #path('assessment-centers/<int:pk>/', views.assessment_center_detail, name='assessment_center_detail'),
    path('assessment-centers/create/', views.assessment_center_create, name='create_assessment_center'),
    path('occupations/', views.occupation_list, name='occupation_list'),
    path('occupations/create/', views.occupation_create, name='occupation_create'),
    path('occupations/<int:pk>/', views.occupation_view, name='occupation_view'),
    path('occupations/<int:pk>/detail/', views.occupation_detail, name='occupation_detail'),
    path('occupations/<int:pk>/update-fees/', views.update_occupation_fees, name='update_occupation_fees'),
    path('occupations/<int:pk>/edit/', views.occupation_edit, name='occupation_edit'),
    path('occupations/<int:occupation_id>/add-level/', views.add_level, name='add_level'),
    
    # UVTAB Fees Module
    path('fees/', views_fees.uvtab_fees_home, name='uvtab_fees_home'),
    path('fees/candidates/', views_fees.candidate_fees_list, name='candidate_fees_list'),
    path('fees/centers/', views_fees.center_fees_list, name='center_fees_list'),
    path('fees/centers/<int:center_id>/candidates/<str:series_id>/', views_fees.center_candidates_report, name='center_candidates_report'),
    path('fees/centers/<int:center_id>/invoice/<str:series_id>/', views_fees.generate_pdf_invoice, name='generate_pdf_invoice'),
    path('fees/centers/mark-as-paid/', views_fees.mark_centers_as_paid, name='mark_centers_as_paid'),
    
    path('modules/add/<int:level_id>/', views.add_module, name='add_module'),
    path('papers/add/<int:level_id>/', views.add_paper, name='add_paper'),
    path('candidates/', views.candidate_list, name='candidate_list'),
    path('results/', views.results_home, name='results_home'),
    path('awards/', views.awards_list, name='awards_list'),
    path('results/generate-marksheet/', views.generate_marksheet, name='generate_marksheet'),
    path('results/download-marksheet/', views.download_marksheet, name='download_marksheet'),
    path('results/print-marksheet/', views.print_marksheet, name='print_marksheet'),
    path('results/download-printed-marksheet/', views.download_printed_marksheet, name='download_printed_marksheet'),
    path('results/upload-marks/', views.upload_marks, name='upload_marks'),
    path('api/occupations/', views.api_occupations, name='api_occupations'),
    path('api/occupations-by-category/', views.api_occupations_by_category, name='api_occupations_by_category'),
    path('complaints/bulk-assign/', views.complaints_bulk_assign, name='complaints_bulk_assign'),
    path('api/all-levels-modules-papers/', views.api_all_levels_modules_papers, name='api_all_levels_modules_papers'),
    path('api/levels/', views.api_levels, name='api_levels'),
    path('api/levels-for-occupation/', views.api_levels_for_occupation, name='api_levels_for_occupation'),
    path('api/levels-for-papers/', views.api_levels_for_papers, name='api_levels_for_papers'),
    path('api/informal-modules-papers/', views_api.api_informal_modules_papers, name='api_informal_modules_papers'),
    path('api/assessment-series/', views_api.api_assessment_series, name='api_assessment_series'),
    path('api/occupations/<int:occupation_id>/add-level/', views_api.api_add_level, name='api_add_level'),
    path('api/occupations/<int:occupation_id>/remove-level/', views_api.api_remove_level, name='api_remove_level'),
    path('api/centers/', views.api_centers, name='api_centers'),
    path('api/occupation-level-structure/', views.api_occupation_level_structure, name='api_occupation_level_structure'),
    path('api/modules/', views.api_modules, name='api_modules'),
    path('api/occupation-category/', views.api_occupation_category, name='api_occupation_category'),
    path('candidates/create/', views.candidate_create, name='candidate_create'),
    path('candidates/<int:id>/', views.candidate_view, name='candidate_view'),
    path('candidates/<int:id>/add-result/', views.add_result, name='add_result'),
    path('candidates/<int:id>/edit-result/', views.edit_result, name='edit_result'),
    path('candidates/<int:id>/enroll/', views.enroll_candidate_view, name='enroll_candidate'),
    path('candidates/<int:id>/clear-enrollment/', views.clear_enrollment, name='clear_enrollment'),
    path('candidates/<int:id>/edit/', views.edit_candidate, name='edit_candidate'),
    path('candidates/<int:id>/regenerate_reg_number/', views.regenerate_candidate_reg_number, name='regenerate_candidate_reg_number'),
    path('candidates/<int:id>/change-center/', views.change_center, name='change_center'),
    path('candidates/<int:id>/change-occupation/', views.change_occupation, name='change_occupation'),
    path('candidates/<int:id>/change-registration-category/', views.change_registration_category, name='change_registration_category'),
    # Secure document serving
    path('candidates/<int:candidate_id>/documents/<str:document_type>/', document_views.serve_candidate_document, name='serve_candidate_document'),
    # Candidate verification
    path('candidates/<int:id>/verify/', views.verify_candidate, name='verify_candidate'),
    path('candidates/<int:id>/decline/', views.decline_candidate, name='decline_candidate'),
    path('api/districts/<int:district_id>/villages/', views.district_villages_api, name='api_district_villages'),
    path('api/assessment-centers/<int:center_id>/branches/', views.api_assessment_center_branches, name='api_assessment_center_branches'),
    path('api/session-status/', views.check_session_status, name='check_session_status'),
    path('assessment-centers/<int:id>/', views.assessment_center_view, name='assessment_center_view'),
    path('assessment-centers/<int:id>/edit/', views.edit_assessment_center, name='edit_assessment_center'),
    
    # Assessment Center Branch URLs
    path('assessment-centers/<int:center_id>/branches/', views.assessment_center_branches, name='assessment_center_branches'),
    path('assessment-centers/<int:center_id>/branches/create/', views.assessment_center_branch_create, name='assessment_center_branch_create'),
    path('assessment-centers/<int:center_id>/branches/<int:branch_id>/edit/', views.assessment_center_branch_edit, name='assessment_center_branch_edit'),
    path('assessment-centers/<int:center_id>/branches/<int:branch_id>/delete/', views.assessment_center_branch_delete, name='assessment_center_branch_delete'), 
    path('modules/', views.module_list, name='module_list'),
    path('papers/', views.paper_list, name='paper_list'),
    path('papers/create/', views.paper_create, name='paper_create'),
    path('papers/<int:pk>/', views.paper_detail, name='paper_detail'),
    path('papers/<int:pk>/edit/', views.paper_edit, name='paper_edit'),
    path('papers/<int:pk>/delete/', views.paper_delete, name='paper_delete'),
    path('papers/bulk-delete/', views.paper_bulk_delete, name='paper_bulk_delete'),
    path('modules/create/', views.module_create, name='module_create'),
    path('modules/<int:pk>/', views.module_detail, name='module_detail'),
    path('modules/edit/<int:pk>/', views.module_edit, name='module_edit'),
    path('modules/<int:pk>/delete/', views.module_delete, name='module_delete'),
    path('modules/bulk-delete/', views.module_bulk_delete, name='module_bulk_delete'),
    path('config/', views.config_home, name='config_home'),
    path('config/districts/', views.district_list, name='district_list'),
    path('config/districts/create/', views.district_create, name='district_create'),
    path('config/villages/', views.village_list, name='village_list'),
    path('config/villages/create/', views.village_create, name='village_create'),
    # Nature of Disability CRUD
    path('config/nature-of-disability/', views.natureofdisability_list, name='natureofdisability_list'),
    path('config/nature-of-disability/create/', views.natureofdisability_create, name='natureofdisability_create'),
    path('config/nature-of-disability/<int:pk>/', views.natureofdisability_view, name='natureofdisability_view'),
    path('config/nature-of-disability/<int:pk>/edit/', views.natureofdisability_edit, name='natureofdisability_edit'),
    path('reports/', views.report_list, name='report_list'),
    path('reports/albums/', views.generate_album, name='generate_album'),
    path('reports/result-list/', views.generate_result_list, name='generate_result_list'),
    path('reports/result-list/download/', views.download_result_list_pdf, name='download_result_list_pdf'),
    path('users/', views.user_home, name='user_home'),
    # Center Representatives
    path('users/center-representatives/', views.view_center_reps, name='view_center_reps'),
    path('users/center-representatives/create/', views.create_center_rep, name='create_center_rep'),
    path('users/center-representatives/<int:pk>/', views.view_center_rep_detail, name='view_center_rep'),
    path('users/center-representatives/<int:pk>/edit/', views.edit_center_rep, name='edit_center_rep'),
    # Support Staff
    path('users/support-staff/', views.view_support_staff, name='view_support_staff'),
    path('users/support-staff/create/', views.create_support_staff, name='create_support_staff'),
    path('users/support-staff/<int:pk>/', views.view_support_staff_detail, name='view_support_staff_detail'),
    path('users/support-staff/<int:pk>/edit/', views.edit_support_staff, name='edit_support_staff'),
    path('candidates/<int:id>/add-regno-to-photo/', views.add_regno_to_photo, name='add_regno_to_photo'),
    path('candidates/<int:id>/transcript/', views.generate_transcript, name='generate_transcript'),
    path('candidates/<int:id>/verified-results/', views.generate_verified_results, name='generate_verified_results'),
    path('candidates/<int:id>/testimonial/', views.generate_testimonial, name='generate_testimonial'),
    path('statistics/', views.statistics_home, name='statistics_home'),
    path('statistics/assessment-series/<int:year>/<int:month>/', views.assessment_series_detail, name='assessment_series_detail'),
    path('statistics/assessment-series/<int:year>/<int:month>/report/', views.generate_performance_report, name='generate_performance_report'),
    # Staff Management
    path('users/staff/', views.staff_list, name='staff_list'),
    path('users/staff/create/', views.staff_create, name='staff_create'),
    path('users/staff/<int:pk>/', views.staff_detail, name='staff_detail'),
    path('users/staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    
    # Assessment Series URLs - Year-based organization
    path('assessment-series/', views.assessment_series_years, name='assessment_series_list'),  # Main entry point - shows years
    path('assessment-series/years/', views.assessment_series_years, name='assessment_series_years'),  # Alternative URL
    path('assessment-series/year/<int:year>/', views.assessment_series_year_detail, name='assessment_series_year_detail'),  # Year detail
    path('assessment-series/create/<int:year>/', views.assessment_series_create_for_year, name='assessment_series_create_for_year'),  # Create for specific year
    path('assessment-series/create/', views.assessment_series_create, name='assessment_series_create'),  # Create without year
    path('assessment-series/<int:pk>/', views.assessment_series_view, name='assessment_series_view'),
    path('assessment-series/<int:pk>/edit/', views.assessment_series_edit, name='assessment_series_edit'),
    path('assessment-series/<int:pk>/delete/', views.assessment_series_delete, name='assessment_series_delete'),
    path('assessment-series/<int:pk>/set-current/', views.assessment_series_set_current, name='assessment_series_set_current'),
    path('assessment-series/<int:pk>/toggle-results/', views.assessment_series_toggle_results, name='assessment_series_toggle_results'),

    # Statistical Reports URLs
    path('statistical-reports/', views.statistical_reports_home, name='statistical_reports'),
    path('statistical-reports/series/<int:pk>/', views.assessment_series_statistical_report, name='assessment_series_statistical_report'),
    
    # Candidate Portal URLs
    path('portal/', views.candidate_portal_login, name='candidate_portal_login'),
    path('portal/logout/', views.candidate_portal_logout, name='candidate_portal_logout'),
    path('portal/candidate/<int:id>/', views.candidate_portal_view, name='candidate_portal_view'),
    
    # Sector URLs
    path('sectors/', sector_views.sector_list, name='sector_list'),
    path('sectors/create/', sector_views.sector_create, name='sector_create'),
    path('sectors/<int:pk>/', sector_views.sector_detail, name='sector_detail'),
    path('sectors/<int:pk>/edit/', sector_views.sector_edit, name='sector_edit'),
    path('sectors/<int:pk>/delete/', sector_views.sector_delete, name='sector_delete'),
    
    # API endpoints
    path('api/assessment-series/', views.api_assessment_series, name='api_assessment_series'),
    
    # Complaints Module
    path('complaints/', views.complaints_list, name='complaints_list'),
    path('complaints/create/', views.complaints_create, name='complaints_create'),
    path('complaints/<int:pk>/', views.complaints_detail, name='complaints_detail'),
    path('complaints/categories/', views.complaint_categories_list, name='complaint_categories_list'),
    path('complaints/categories/<int:pk>/edit/', views.complaint_category_edit, name='complaint_category_edit'),
    path('complaints/categories/<int:pk>/delete/', views.complaint_category_delete, name='complaint_category_delete'),
    path('complaints/helpdesk-teams/', views.helpdesk_teams_list, name='helpdesk_teams_list'),
    path('complaints/helpdesk-teams/<int:pk>/edit/', views.helpdesk_team_edit, name='helpdesk_team_edit'),
    path('complaints/helpdesk-teams/<int:pk>/delete/', views.helpdesk_team_delete, name='helpdesk_team_delete'),
    path('complaints/attachment/<int:attachment_id>/', views.complaint_attachment_view, name='complaint_attachment_view'),
 ]
