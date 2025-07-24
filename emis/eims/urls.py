from django.urls import path
from . import views
from . import views_api
from django.contrib.auth import views as auth_views




urlpatterns = [
    path('candidates/import-dual/', views.candidate_import_dual, name='candidate_import_dual'),
    path('candidates/bulk-action/', views.bulk_candidate_action, name='bulk_candidate_action'),
    path('candidates/bulk-modules/', views.bulk_candidate_modules, name='bulk_candidate_modules'),
    #path('create/', views.eims_create, name='eims_create'),
    # add more views later

    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('assessment-centers/', views.assessment_center_list, name='assessment_center_list'),
    #path('assessment-centers/<int:pk>/', views.assessment_center_detail, name='assessment_center_detail'),
    path('assessment-centers/create/', views.assessment_center_create, name='create_assessment_center'),
    path('occupations/', views.occupation_list, name='occupation_list'),
    path('occupations/create/', views.occupation_create, name='occupation_create'),
    path('occupations/<int:pk>/', views.occupation_view, name='occupation_view'),
    path('occupations/<int:pk>/detail/', views.occupation_detail, name='occupation_detail'),
    path('occupations/<int:pk>/edit/', views.occupation_edit, name='occupation_edit'),
    path('occupations/<int:occupation_id>/add-level/', views.add_level, name='add_level'),
    path('modules/add/<int:level_id>/', views.add_module, name='add_module'),
    path('papers/add/<int:level_id>/', views.add_paper, name='add_paper'),
    path('candidates/', views.candidate_list, name='candidate_list'),
    path('results/', views.results_home, name='results_home'),
    path('results/generate-marksheet/', views.generate_marksheet, name='generate_marksheet'),
    path('results/download-marksheet/', views.download_marksheet, name='download_marksheet'),
    path('results/print-marksheet/', views.print_marksheet, name='print_marksheet'),
    path('results/download-printed-marksheet/', views.download_printed_marksheet, name='download_printed_marksheet'),
    path('results/upload-marks/', views.upload_marks, name='upload_marks'),
    path('api/occupations/', views.api_occupations, name='api_occupations'),
    path('api/levels/', views.api_levels, name='api_levels'),
    path('api/levels-for-occupation/', views.api_levels_for_occupation, name='api_levels_for_occupation'),
    path('api/informal-modules-papers/', views_api.api_informal_modules_papers, name='api_informal_modules_papers'),
    path('api/occupations/<int:occupation_id>/add-level/', views_api.api_add_level, name='api_add_level'),
    path('api/occupations/<int:occupation_id>/remove-level/', views_api.api_remove_level, name='api_remove_level'),
    path('api/centers/', views.api_centers, name='api_centers'),
    path('api/occupation-level-structure/', views.api_occupation_level_structure, name='api_occupation_level_structure'),
    path('api/modules/', views.api_modules, name='api_modules'),
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
    path('api/districts/<int:district_id>/villages/', views.district_villages_api, name='api_district_villages'),
    path('assessment-centers/<int:id>/', views.assessment_center_view, name='assessment_center_view'),
    path('assessment-centers/<int:id>/edit/', views.edit_assessment_center, name='edit_assessment_center'), 
    path('modules/', views.module_list, name='module_list'),
    path('papers/', views.paper_list, name='paper_list'),
    path('papers/create/', views.paper_create, name='paper_create'),
    path('papers/<int:pk>/', views.paper_detail, name='paper_detail'),
    path('papers/<int:pk>/edit/', views.paper_edit, name='paper_edit'),
    path('modules/create/', views.module_create, name='module_create'),
    path('modules/<int:pk>/', views.module_detail, name='module_detail'),
    path('modules/edit/<int:pk>/', views.module_edit, name='module_edit'),
    path('modules/<int:pk>/delete/', views.module_delete, name='module_delete'),
    path('fees-types/', views.fees_type_list, name='fees_type_list'),
    path('fees-types/create/', views.fees_type_create, name='fees_type_create'),
    path('fees-types/<int:pk>/edit/', views.fees_type_edit, name='fees_type_edit'),
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
    path('statistics/', views.statistics_home, name='statistics_home'),
    path('statistics/assessment-series/<int:year>/<int:month>/', views.assessment_series_detail, name='assessment_series_detail')
    

 ]    



  
