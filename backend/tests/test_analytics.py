import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.core.exceptions import InputError
from app.schemas.analytics import BatchFilters, PublicationPayload
from app.services.analytics import validate_payload
from app.services.analytics_artifacts import load_publication


class AnalyticsContractTests(unittest.TestCase):
    def setUp(self):
        self.payload=load_publication("v2-controlled")

    def test_actual_approved_payload(self):
        validate_payload(self.payload)
        self.assertEqual(self.payload.tasks_summary.completion_rate.percent,"50.000000")

    def test_199_of_200_keeps_fraction(self):
        p=load_publication("v1-boundary");validate_payload(p)
        self.assertEqual(p.tasks_summary.completion_rate.percent,"99.500000")

    def test_daily_cannot_disagree_with_ADS(self):
        p=self.payload.model_copy(deep=True);p.daily[0].known_minutes+=1
        with self.assertRaises(InputError):validate_payload(p)

    def test_cancelled_stays_in_denominator(self):
        p=self.payload.model_copy(deep=True);p.tasks_summary.total-=1
        with self.assertRaises(InputError):validate_payload(p)

    def test_bad_ratio_rejected(self):
        p=self.payload.model_copy(deep=True);p.topic_summary.confirmation_rate.percent="100.000000"
        with self.assertRaises(InputError):validate_payload(p)

    def test_duplicate_day_rejected(self):
        p=self.payload.model_copy(deep=True);p.daily.append(p.daily[0])
        with self.assertRaises(InputError):validate_payload(p)

    def test_unknown_duration_not_zeroed(self):
        p=self.payload.model_copy(deep=True);p.records_summary.missing_duration_count=0
        with self.assertRaises(InputError):validate_payload(p)

    def test_quality_failure_rejected(self):
        p=self.payload.model_copy(deep=True);p.quality["fatal_errors"]=1
        with self.assertRaises(InputError):validate_payload(p)

    def test_synthetic_and_unknown_rules_rejected(self):
        data=self.payload.model_dump(mode="json")
        for field,value in [("dataset_kind","synthetic"),("rule_version","quality-1.1")]:
            changed=copy.deepcopy(data);changed[field]=value
            with self.assertRaises(ValidationError):PublicationPayload.model_validate(changed)

    def test_unknown_job_or_path_rejected(self):
        for job in ("v1-scale","../v2-controlled","v1-D07"):
            with self.assertRaises(InputError):load_publication(job)

    def test_filters_limit_dates_and_owner_input(self):
        for values in ({"page_size":51},{"period_start":"2026-01-01"},{"period_start":"2026-01-01","period_end":"2026-12-01"},{"owner_user_id":4},{"dataset_kind":"synthetic"}):
            with self.assertRaises(ValidationError):BatchFilters.model_validate(values)

    def test_distinct_empty_list_meanings(self):
        from unittest.mock import Mock
        from app.services.analytics import AnalyticsService
        for total,available,reason in [(0,0,"no_completed_batch"),(0,2,"no_matching_batch"),(4,4,"page_empty")]:
            repo=Mock();repo.list_visible.return_value=([],total,available)
            self.assertEqual(AnalyticsService(repo).list_batches(3,BatchFilters()).empty_reason,reason)


if __name__=="__main__":unittest.main()
