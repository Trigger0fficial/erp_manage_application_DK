from tkinter.font import names

from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .views import *
from .views import show_error_404

handler404 = 'server.views.show_error_404'

urlpatterns = [
    path('', show_index, name='home'),
    path('register', show_register, name='register'),
    path('login', show_auth, name='login'),
    path('profile', show_profile, name='profile'),
    path('admin_index', show_index_admin, name='admin_index'),
    path('application/<int:pk>', show_application, name='application'),
    path('list_call_note/<int:pk>', show_list_call_note, name='list_call_note'),
    path('report_admin/<int:pk>', show_report_admin, name='report_admin'),
    path('list_application', show_list_applications, name='list_application'),
    path('add_application', show_add_application, name='add_application'),
    path('person_manage', show_person_manage, name='person_manage'),
    path('list_records_call', show_notifications, name='list_records_call'),
    path('not_access', show_error_403, name='not_access')

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)