from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Candidate
from .utils.regno_stamp import add_regno_to_image


# @receiver(post_save, sender=Candidate)
# def restamp_candidate_photo(sender, instance: 'Candidate', created, **kwargs):
#     """
#     Whenever a Candidate is saved AND the reg-number changed,
#     stamp/over-stamp the photo with the current reg-number.
#     """
#     # we need the previous value; only exists when NOT 'created'
#     if created:
#         old_reg = None
#     else:
#         old_reg = sender.objects.filter(pk=instance.pk).values_list("reg_number", flat=True).first()
#
#     # if there's no photo or reg number, nothing to do
#     if not instance.passport_photo or not instance.reg_number:
#         return
#     # only stamp if reg-number is new or changed
#     if created or (old_reg != instance.reg_number):
#         add_regno_to_image(instance.passport_photo.path, instance.reg_number)
