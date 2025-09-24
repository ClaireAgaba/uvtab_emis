from django.test import TestCase
from datetime import date

from .models import (
    District,
    Village,
    AssessmentCenterCategory,
    AssessmentCenter,
    OccupationCategory,
    Occupation,
    Level,
    OccupationLevel,
    Candidate,
)


class CandidateRegNumberTests(TestCase):
    """Regression tests for candidate registration number generation/regeneration."""

    def setUp(self):
        # Minimal fixtures for creating candidates
        self.district = District.objects.create(name="Kampala", region="Central")
        self.village = Village.objects.create(name="Central Village", district=self.district)
        self.center_cat = AssessmentCenterCategory.objects.create(name="TVET")
        self.center = AssessmentCenter.objects.create(
            center_number="UVT001",
            center_name="UVTAB Main Center",
            category=self.center_cat,
            district=self.district,
            village=self.village,
        )
        self.occ_cat = OccupationCategory.objects.create(name="Technical")
        self.occupation = Occupation.objects.create(code="PR", name="Phone Repairer", category=self.occ_cat)

    def _base_candidate_kwargs(self):
        return dict(
            full_name="Test Candidate",
            date_of_birth=date(2000, 1, 1),
            gender="M",
            nationality="Ugandan",
            district=self.district,
            village=self.village,
            assessment_center=self.center,
            entry_year=2025,
            intake="M",
            occupation=self.occupation,
            assessment_date=date(2025, 3, 15),
        )

    def test_reg_number_generation_and_serial_grouping(self):
        # First candidate (Formal)
        c1 = Candidate.objects.create(
            registration_category="Formal",
            **self._base_candidate_kwargs(),
        )
        self.assertIsNotNone(c1.reg_number)
        self.assertIn("UVT001", c1.reg_number)
        self.assertIn("/F/", c1.reg_number)
        self.assertTrue(c1.reg_number.endswith("/001"))

        # Second candidate (Formal) in same group → serial increments
        c2_kwargs = self._base_candidate_kwargs().copy()
        c2_kwargs['full_name'] = "Test Candidate Two"
        c2 = Candidate.objects.create(
            registration_category="Formal",
            **c2_kwargs,
        )
        self.assertTrue(c2.reg_number.endswith("/002"))

        # Change registration category for c2 to Modular, then regenerate regno by clearing it
        c2.registration_category = "Modular"
        c2.reg_number = None
        c2.save()

        self.assertIn("/M/", c2.reg_number)
        self.assertTrue(c2.reg_number.endswith("/001"))


class ModularFeesCalculationTests(TestCase):
    """Regression tests for Modular enrollment fee calculation and caching."""

    def setUp(self):
        self.district = District.objects.create(name="Wakiso", region="Central")
        self.village = Village.objects.create(name="Nansana", district=self.district)
        self.center_cat = AssessmentCenterCategory.objects.create(name="BTVET")
        self.center = AssessmentCenter.objects.create(
            center_number="UVT002",
            center_name="UVTAB Branch Center",
            category=self.center_cat,
            district=self.district,
            village=self.village,
        )
        self.occ_cat = OccupationCategory.objects.create(name="Electrical")
        self.occupation = Occupation.objects.create(code="ELC", name="Electrical Installation", category=self.occ_cat, has_modular=True)
        self.level = Level.objects.create(
            name="Level 1 ELC",
            occupation=self.occupation,
            modular_fee_single=30000,
            modular_fee_double=45000,
        )
        # Link occupation and level for fee lookup logic used by calculate_fees_balance
        OccupationLevel.objects.create(occupation=self.occupation, level=self.level, structure_type='modules')

    def _create_modular_candidate(self):
        return Candidate.objects.create(
            full_name="Modular Candidate",
            date_of_birth=date(2001, 2, 2),
            gender="F",
            nationality="Ugandan",
            district=self.district,
            village=self.village,
            assessment_center=self.center,
            entry_year=2025,
            intake="A",
            occupation=self.occupation,
            registration_category="Modular",
            assessment_date=date(2025, 8, 15),
        )

    def test_modular_fees_by_module_count(self):
        cand = self._create_modular_candidate()

        # 1 module → 30,000
        cand.modular_module_count = 1
        cand.modular_billing_amount = None
        cand.update_fees_balance()
        self.assertEqual(float(cand.fees_balance), 30000.0)

        # 2 modules → 45,000
        cand.modular_module_count = 2
        cand.modular_billing_amount = None
        cand.update_fees_balance()
        self.assertEqual(float(cand.fees_balance), 45000.0)

    def test_modular_billing_amount_caching_used_when_present(self):
        cand = self._create_modular_candidate()
        cand.modular_module_count = 2  # would normally be 45,000
        cand.modular_billing_amount = 35000  # cached negotiated amount
        cand.update_fees_balance()
        self.assertEqual(float(cand.fees_balance), 35000.0)
