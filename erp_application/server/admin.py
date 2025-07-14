from django.contrib import admin
from .models import *


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'plan_work')
    list_filter = ('role',)
    search_fields = ('user__username', 'plan_work')
    list_editable = ('role',)


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'full_address', 'status')
    list_filter = ('status', )
    search_fields = ('farmer', 'full_address', 'region')
    list_editable = ('status',)


@admin.register(FarmerContact)
class FarmerContactAdmin(admin.ModelAdmin):
    list_display = ('contact', 'type', 'is_work', 'farmer')
    list_filter = ('type', 'is_work')
    search_fields = ('contact',)
    list_editable = ('is_work',)


class FarmerContactInline(admin.TabularInline):
    model = FarmerContact
    extra = 1


class HistoryContactInline(admin.TabularInline):
    model = HistoryContact
    extra = 1


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'farmer', 'manage', 'status', 'inn', 'product', 'date_delivery', 'price_nds')
    list_filter = ('status', 'manage', 'date_delivery')
    search_fields = ('farmer__farmer', 'inn', 'product')
    list_editable = ('status',)
    inlines = [HistoryContactInline]  # Вложенная история звонков


@admin.register(HistoryContact)
class HistoryContactAdmin(admin.ModelAdmin):
    list_display = ('application', 'data', 'dsc')
    list_filter = ('data',)
    search_fields = ('dsc', 'application__id')

@admin.register(CorpPassword)
class CorpPasswordAdmin(admin.ModelAdmin):
    list_filter = ('date',)

@admin.register(ApplicationTransferHistory)
class ApplicationTransferHistoryAdmin(admin.ModelAdmin):
    list_display = ('application', 'from_user', 'to_user', 'transfer_date')
    list_filter = ('transfer_date',)

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'manage')
    list_filter = ('manage', )
    search_fields = ('name', )
