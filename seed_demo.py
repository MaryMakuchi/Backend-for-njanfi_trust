"""Seed the demo group "Nfah Njangi 2026" with six members.

Run on your local machine:
    python manage.py shell < seed_demo.py

Idempotent: re-running updates the same records instead of duplicating.
All users share the password below.
"""
from datetime import date, time

from django.contrib.auth import get_user_model

from groups.models import NjangiGroup, GroupMembership

User = get_user_model()

PASSWORD = 'Njangi2026!'

# (full_name, email, phone, role)
MEMBERS = [
    ('Eustace Nfah',    'eustace.nfah@demo.com',   '+237650000001', 'president'),
    ('Delphine Nfah',   'delphine.nfah@demo.com',  '+237650000002', 'treasurer'),
    ('Thelma Balike',   'thelma.balike@demo.com',  '+237650000003', 'member'),
    ('Theresia Ngonda', 'theresia.ngonda@demo.com','+237650000004', 'member'),
    ('Ndeh Mark',       'ndeh.mark@demo.com',      '+237650000005', 'member'),
    ('Juliana Makuchi', 'juliana.makuchi@demo.com','+237650000006', 'member'),
    ('Mary Makuchi',    'makuchinfah@gmail.com',   '+237650000007', 'member'),
]

users = {}
for full_name, email, phone, role in MEMBERS:
    user, created = User.objects.get_or_create(
        email=email,
        defaults={'full_name': full_name, 'phone': phone},
    )
    user.full_name = full_name
    user.phone = phone
    user.is_kyc_verified = True
    user.phone_verified = True
    user.email_verified = True
    user.set_password(PASSWORD)
    user.save()
    users[email] = user
    print(f"{'Created' if created else 'Updated'} user: {full_name} <{email}>")

president = users['eustace.nfah@demo.com']

group, gcreated = NjangiGroup.objects.get_or_create(
    name='Nfah Njangi 2026',
    defaults={
        'contribution_amount': 5000,
        'frequency': 'Monthly',
        'max_members': len(MEMBERS),
        'start_date': date(2026, 6, 28),
        'duration_months': 7,
        'picking_mode': 'mri_weighted',
        'created_by': president,
        'rules': 'Njangi sits the first Sunday of every month, deadline 6:00 PM. '
                 'Starts 28 June 2026, final sitting first Sunday of January 2027.',
    },
)
# Monthly, first Sunday, 6 PM deadline. weekday: Mon=0 .. Sun=6
group.contribution_amount = 5000
group.frequency = 'Monthly'
group.max_members = len(MEMBERS)
group.start_date = date(2026, 6, 28)
group.duration_months = 7
group.picking_mode = 'mri_weighted'
group.play_frequency = 'monthly'
group.play_week_of_month = 'first'
group.play_weekday = 6            # Sunday
group.play_deadline_time = time(18, 0)
group.created_by = president
if not group.invitation_code:
    group.invitation_code = 'NFAH2026'
group.save()
print(f"\n{'Created' if gcreated else 'Updated'} group: {group.name} (code: {group.invitation_code})")

for position, (full_name, email, phone, role) in enumerate(MEMBERS, start=1):
    membership, mcreated = GroupMembership.objects.get_or_create(
        group=group,
        user=users[email],
        defaults={'role': role, 'rotation_position': position},
    )
    membership.role = role
    membership.rotation_position = position
    membership.save()
    print(f"  {position}. {full_name} -> {role}")

print('\nDone. Login credentials (password is the same for everyone):')
print(f'  Password: {PASSWORD}\n')
for full_name, email, phone, role in MEMBERS:
    print(f'  {full_name:18} {email:28} ({role})')
