from django.contrib import admin

from .models import AgentAction


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'agent', 'action', 'property', 'reason')
    list_filter = ('action',)
    search_fields = ('reason', 'property__Property_Name', 'agent__name')
    list_select_related = ('agent', 'property')
