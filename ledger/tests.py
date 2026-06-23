import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from groups.models import GroupMembership, NjangiGroup
from ledger.models import Transaction

User = get_user_model()


class GroupLedgerViewTests(TestCase):
    def _mk(self):
        s = uuid.uuid4().hex[:10]
        return User.objects.create_user(email=s + '@t.co', password='x', phone='+237' + s[:8])

    def setUp(self):
        self.member = self._mk()
        self.outsider = self._mk()
        self.group = NjangiGroup.objects.create(
            name='LT', contribution_amount=Decimal('100'), max_members=3, start_date=date.today(),
        )
        GroupMembership.objects.create(group=self.group, user=self.member, role='member')
        for t in ['contribution', 'payout', 'savings_deposit', 'savings_withdrawal',
                  'loan_disbursement', 'social_fund']:
            Transaction.objects.create(
                user=self.member, group=self.group, title=t, amount=Decimal('10'), transaction_type=t,
            )
        self.base = f'/api/v1/groups/{self.group.id}/ledger/'

    def _types(self, resp):
        return sorted({x['type'] for x in resp.data['results']})

    def test_categories_and_membership(self):
        c = APIClient()
        c.force_authenticate(self.member)
        r = c.get(self.base + '?category=all')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['results']), 6)
        self.assertEqual(self._types(c.get(self.base + '?category=njangi')), ['contribution', 'payout'])
        self.assertEqual(self._types(c.get(self.base + '?category=savings')),
                         ['savings_deposit', 'savings_withdrawal'])
        self.assertEqual(self._types(c.get(self.base + '?category=loans')), ['loan_disbursement'])
        self.assertEqual(self._types(c.get(self.base + '?category=social_fund')), ['social_fund'])
        # newest first
        dates = [x['date'] for x in r.data['results']]
        self.assertEqual(dates, sorted(dates, reverse=True))

        c2 = APIClient()
        c2.force_authenticate(self.outsider)
        self.assertEqual(c2.get(self.base + '?category=all').status_code, 403)
