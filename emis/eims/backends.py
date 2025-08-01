from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from .models import Staff, SupportStaff

User = get_user_model()

class StatusCheckBackend(ModelBackend):
    """
    Custom authentication backend that checks staff/support staff status
    before allowing login.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        print(f"DEBUG: StatusCheckBackend.authenticate() called for username: {username}")
        
        # First, use the default authentication
        user = super().authenticate(request, username, password, **kwargs)
        
        if user is None:
            print(f"DEBUG: Default authentication failed for username: {username}")
            return None
        
        print(f"DEBUG: Authenticating user: {user.username}")
        
        # Check if user is staff or support staff and verify their status
        try:
            # Check if user has a staff profile
            if hasattr(user, 'staff_profile'):
                staff = user.staff_profile
                print(f"DEBUG: User has staff profile, status: {staff.status}")
                if staff.status == 'Inactive':
                    print(f"DEBUG: Denying login for inactive staff: {user.username}")
                    return None  # Deny login for inactive staff
            
            # Check if user has a support staff profile
            elif hasattr(user, 'supportstaff'):
                support_staff = user.supportstaff
                print(f"DEBUG: User has support staff profile, status: {support_staff.status}")
                if support_staff.status == 'Inactive':
                    print(f"DEBUG: Denying login for inactive support staff: {user.username}")
                    return None  # Deny login for inactive support staff
            else:
                print(f"DEBUG: User {user.username} has no staff profile - allowing login")
            
            # For regular users without staff profiles, allow login
            print(f"DEBUG: Allowing login for user: {user.username}")
            return user
            
        except (Staff.DoesNotExist, SupportStaff.DoesNotExist) as e:
            print(f"DEBUG: Exception occurred: {e}")
            # If no staff profile exists, allow login (regular users)
            return user
    
    def user_can_authenticate(self, user):
        """
        Override to check staff status in addition to is_active
        """
        if not super().user_can_authenticate(user):
            return False
        
        # Additional check for staff status
        try:
            if hasattr(user, 'staff_profile'):
                return user.staff_profile.status == 'Active'
            elif hasattr(user, 'supportstaff'):
                return user.supportstaff.status == 'Active'
            else:
                return True  # Regular users without staff profiles
        except (Staff.DoesNotExist, SupportStaff.DoesNotExist):
            return True
