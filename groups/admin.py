from django.contrib import admin

from groups.models import GroupMembership, NjangiGroup


class MembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


@admin.register(NjangiGroup)
class NjangiGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_count', 'max_members', 'fund_balance', 'invitation_code')
    search_fields = ('name', 'invitation_code')
    inlines = [MembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'role', 'rotation_position', 'is_current_beneficiary')
    list_filter = ('role', 'is_current_beneficiary')
