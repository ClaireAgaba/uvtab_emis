from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from eims.models import Staff


class Command(BaseCommand):
    help = 'Reset passwords for existing IT and Admin staff users'

    def handle(self, *args, **options):
        # Find all Staff users with IT or Admin departments
        it_staff = Staff.objects.filter(department='IT')
        admin_staff = Staff.objects.filter(department='Admin')
        
        updated_count = 0
        
        # Reset IT staff passwords
        for staff in it_staff:
            if staff.user:
                staff.user.set_password('Uvtab@2025')
                staff.user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Reset password for IT user: {staff.user.username}'
                    )
                )
        
        # Reset Admin staff passwords
        for staff in admin_staff:
            if staff.user:
                staff.user.set_password('Uvtab@2025')
                staff.user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Reset password for Admin user: {staff.user.username}'
                    )
                )
        
        if updated_count == 0:
            self.stdout.write(
                self.style.WARNING('No IT or Admin staff users found to update')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully reset passwords for {updated_count} users'
                )
            )
            self.stdout.write('All IT and Admin users now use password: Uvtab@2025')
