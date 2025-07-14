from collections import defaultdict
from datetime import date, timedelta, timezone
from django.utils import timezone as django_timezone

from django.db.models import Case, When, Value, IntegerField

from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Avg, F, Sum, FloatField, IntegerField
from django.db.models.functions import Coalesce
from datetime import timedelta
from .decorators import role_required

from erp_application.asgi import application
from server.forms import *
from webcolors import names

from .forms import CallForm, HistoryContactForm
from .models import *



def show_error_404(req, exception):
    user_role = None
    if req.user.is_authenticated:
        try:
            user_role = req.user.profile.role
        except Profile.DoesNotExist:
            pass
    return render(req, 'server/errors-404-error.html', status=404, context={'user_role': user_role})




def show_register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Извлекаем данные из формы
            user = form.save(commit=False)
            corporate_password = form.cleaned_data.get("corp_password")
            is_senior_manager = form.cleaned_data.get("is_senior_manager", False)

            # Получаем корпоративные пароли (берем последний актуальный)
            try:
                corp_password = CorpPassword.objects.latest("date")
            except CorpPassword.DoesNotExist:
                form.add_error("corp_password", "Ошибка системы: не найден корпоративный пароль.")
                return render(request, "server/signup.html", {"form": form})

            # Проверяем корпоративный пароль для старшего менеджера или обычного менеджера
            if is_senior_manager:
                expected_password = corp_password.total_manage  # Пароль для старшего менеджера
                user_role = Profile.Role.SALES_DIRECTOR
            else:
                expected_password = corp_password.manage  # Пароль для менеджера
                user_role = Profile.Role.MANAGER

            # Проверка корпоративного пароля
            if corporate_password != expected_password:
                form.add_error("corp_password",
                               "Корпоративный пароль не верный, проверьте корректность ввода и/или обратитесь к Администратору компании")
                return render(request, "server/signup.html", {"form": form})

            # Если все проверки прошли успешно, сохраняем пользователя
            user.set_password(form.cleaned_data["password"])
            user.save()
            Profile.objects.create(user=user, role=user_role)

            # Авторизация пользователя и перенаправление
            login(request, user)
            return redirect("login")  # Или нужный маршрут после регистрации

        else:
            # В случае, если форма невалидна, добавляем общую ошибку
            messages.error(request, "Некорректно введены данные. Пожалуйста, исправьте ошибки и попробуйте снова.")
            return render(request, "server/signup.html", {"form": form})

    else:
        form = RegisterForm()

    return render(request, "server/signup.html", {"form": form})


def show_auth(req):
    if req.method == "POST":
        form = LoginForm(req.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(req, username=username, password=password)
            if user is not None:
                login(req, user)

                # Получаем профиль
                try:
                    profile = user.profile
                except Profile.DoesNotExist:
                    messages.error(req, "Профиль пользователя не найден.")
                    return redirect('login')

                # Редирект в зависимости от роли
                if profile.role in [Profile.Role.MANAGER, Profile.Role.SALES_DIRECTOR]:
                    return redirect("home")
                elif profile.role in [Profile.Role.DIRECTOR, Profile.Role.LOGISTICS_DIRECTOR]:
                    return redirect("admin_index")
                else:
                    return redirect("home")  # по умолчанию
            else:
                messages.error(req, "Неверный логин или пароль. Пожалуйста, попробуйте снова.")
    else:
        form = LoginForm()

    return render(req, 'server/signin.html', {'form': form})

@role_required(['Менеджер', 'Старший менеджер'])
def show_index(req):
    user = req.user
    today = date.today()
    seven_days_ago = today - timedelta(days=7)
    fourteen_days_ago = today - timedelta(days=14)

    # Получаем профиль и закреплённые регионы
    profile = Profile.objects.select_related('user').get(user=user)
    assigned_regions = Region.objects.filter(manage=profile)

    # ====================== ФЕРМЕРЫ ======================

    # Подгружаем сразу контакты для оптимизации
    farmer_queryset = Farmer.objects.filter(status='Free') \
        .prefetch_related(
            Prefetch('farmercontact_set', queryset=FarmerContact.objects.filter(type__in=['Phone', 'Mail']))
        )[:1000]

    farmer_data = []
    for farmer in farmer_queryset:
        phone = next((c.contact for c in farmer.farmercontact_set.all() if c.type == 'Phone'), 'Нет телефона')
        mail = next((c.contact for c in farmer.farmercontact_set.all() if c.type == 'Mail'), 'Нет почты')
        farmer_data.append({
            'farmer': farmer,
            'address': farmer.full_address,
            'phone': phone,
            'mail': mail,
            'status': farmer.status,
        })

    # ====================== ЗАЯВКИ ======================

    applications = Application.objects.filter(manage__user=user) \
        .select_related('farmer', 'manage__user')

    application_data = []
    for app in applications:
        price_with_nds = round(app.price_nds * (1 + app.nds / 100), 2) if app.price_nds and app.nds is not None else None
        application_data.append({
            'farmer': app.farmer,
            'product': app.product or 'Отсутствует',
            'product_quality': app.product_quality or 'Отсутствует',
            'price': f'{app.price_nds}/{price_with_nds}' if price_with_nds else 'Отсутствует',
            'date_delivery': app.date_delivery or 'Отсутствует',
            'manager_name': f'{app.manage.user.first_name or "Отсутствует"} {app.manage.user.last_name or "Отсутствует"}',
            'status': app.status or 'Отсутствует'
        })

    # ====================== СТАТИСТИКА ======================

    # -- 1. Заявки в работе
    STATUSES_IN_WORK = ['Not_processed', 'Primary_contact', 'Approval', 'Revision']
    in_work_total = applications.filter(status__in=STATUSES_IN_WORK).count()

    current_week = applications.filter(
        status__in=STATUSES_IN_WORK,
        data_start__range=(seven_days_ago, today)
    ).count()

    previous_week = applications.filter(
        status__in=STATUSES_IN_WORK,
        data_start__range=(fourteen_days_ago, seven_days_ago)
    ).count()

    percent_diff = round(((current_week - previous_week) / previous_week) * 100, 2) if previous_week > 0 else (100 if current_week > 0 else 0)

    # -- 2. Согласованные / Несогласованные
    approved_count = applications.filter(status='Agreed').count()
    rejected_count = applications.filter(status__in=['Refusal', 'Freezing', 'Not_agreed']).count()

    total_decided = approved_count + rejected_count
    approval_ratio = round((approved_count / total_decided) * 100, 2) if total_decided > 0 else 0.0

    # -- 3. План
    farmers_in_regions = Farmer.objects.filter(region__in=assigned_regions)
    foreign_applications = Application.objects.filter(
        farmer__in=farmers_in_regions
    ).exclude(manage=profile).exclude(status__in=['Refusal', 'Freezing'])

    occupied_farmer_ids = foreign_applications.values_list('farmer_id', flat=True)
    planned_farmers = farmers_in_regions.exclude(id__in=occupied_farmer_ids)

    list_planned_farmers = planned_farmers.prefetch_related(
        Prefetch('farmercontact_set', queryset=FarmerContact.objects.filter(type__in=['Phone', 'Mail']))
    )

    planned_farmer_data = []
    for farmer in planned_farmers:
        phone = next((c.contact for c in farmer.farmercontact_set.all() if c.type == 'Phone'), 'Нет телефона')
        mail = next((c.contact for c in farmer.farmercontact_set.all() if c.type == 'Mail'), 'Нет почты')
        planned_farmer_data.append({
            'farmer': farmer,
            'region': farmer.region.name,
            'address': farmer.full_address,
            'phone': phone,
            'mail': mail,
            'status': farmer.status,
        })


    plan_total = planned_farmers.count()
    plan_done = Application.objects.filter(manage=profile, farmer__in=planned_farmers).count()
    plan_agreed = Application.objects.filter(manage=profile, farmer__in=planned_farmers, status='Agreed').count()
    plan_percent = round((plan_done / plan_total) * 100, 2) if plan_total > 0 else 0.0

    # -- 4. Звонки
    call_count = HistoryContact.objects.filter(type='Call', application__manage=profile).count()
    application_total = applications.count()
    call_avg = round(call_count / application_total, 2) if application_total > 0 else 0.0

    # -- 5. Динамика заявок (30 дней)
    now = django_timezone.now().date()
    start_current = now - timedelta(days=30)
    start_previous = now - timedelta(days=60)
    end_previous = start_current

    current_30 = applications.filter(data_start__gte=start_current).count()
    previous_30 = applications.filter(data_start__range=(start_previous, end_previous)).count()

    delta_percent = round(((current_30 - previous_30) / previous_30) * 100, 2) if previous_30 > 0 else (100.0 if current_30 > 0 else 0.0)
    delta_percent = max(min(delta_percent, 100), -100)

    # -- 6. Объёмы
    agreed_apps = applications.filter(status='Agreed')

    total_volume = agreed_apps.aggregate(sum=Sum('volume'))['sum'] or 0
    current_30_volume = agreed_apps.filter(data_start__gte=start_current).aggregate(sum=Sum('volume'))['sum'] or 0
    previous_30_volume = agreed_apps.filter(data_start__range=(start_previous, end_previous)).aggregate(sum=Sum('volume'))['sum'] or 0

    if previous_30_volume > 0:
        volume_percent_change = round(((current_30_volume - previous_30_volume) / previous_30_volume) * 100, 2)
        volume_percent_change = max(min(volume_percent_change, 100), -100)
    else:
        volume_percent_change = 100.0 if current_30_volume > 0 else 0.0

    # -- 7. Топ-регион
    top_region = agreed_apps.values('farmer__region__name') \
        .annotate(region_count=Count('id')) \
        .order_by('-region_count') \
        .first()

    if top_region and agreed_apps.exists():
        region_name = top_region['farmer__region__name']
        region_count = top_region['region_count']
        region_percent = round((region_count / agreed_apps.count()) * 100, 2)
    else:
        region_name = "Нет данных"
        region_count = 0
        region_percent = 0.0

    # ====================== Формируем итог ======================

    data_statistic = {
        "application": [in_work_total, current_week, percent_diff],
        "approved": [approved_count, rejected_count, approval_ratio],
        'plan': [plan_done, plan_total, plan_agreed, plan_percent],
        'calls': [call_count, delta_percent, call_avg],
        'tons': [total_volume, volume_percent_change, current_30_volume],
        'top_region': [region_name, region_count, region_percent],
    }
    print(planned_farmers)
    context = {
        'planned_farmers': planned_farmer_data,
        'farmers': farmer_data,
        'applications': application_data,
        'data_statistic': data_statistic
    }

    return render(req, 'server/index.html', context)

def show_profile(req):
    return render(req, 'server/user-profile.html')

@login_required
@role_required(['Директор по логистике', 'Директор'])
def show_index_admin(req):
    total_application = Application.objects.all()
    total_farmer = Farmer.objects.all()
    total_manage = Profile.objects.filter()

    applications_work = Application.objects.filter(status__in=['Primary_contact', 'Revision'])
    total_application_count = Application.objects.filter(status='Agreed')

    total_sum = 0
    total_sum_count = 0
    total_person = 0
    total_person_count = 0

    for el in total_application_count:
        total_sum_count += 1
        total_sum += el.price_nds

    for el in total_manage:
        if el.role == 1 or el.role == 4:
            total_person += 1
            total_app = 0
            price_app = 0
            for app in total_application:
                if app.status == 'Agreed' and app.manage.id == el.id:
                    total_app += 1
                    price_app += app.price_nds
            total_person_count += price_app / total_app if total_app != 0 else 0



    data_total_info = {
        'total_sum': [total_sum, total_sum/total_sum_count if total_sum_count!= 0 else 0],
        'total_manage': [total_person, total_person_count, total_person_count/total_person if total_person !=0 else 0],
        'total_1': 0,
        'total_2': 0,
        'total_farmer_app': [total_farmer.count(), total_application_count.count(),
                            (round(100 * total_application_count.count() / total_farmer.count()) if total_farmer.count() != 0 else 0)]

    }
    person = []
    for el in Profile.objects.all():
        count_app_in_work = 0
        if el.role == 1 or el.role == 4:
            count_app = 0
            count_app_agreed = 0
            for app in total_application:
                if app.manage == el:
                    if app.status == 'Agreed':
                        count_app_agreed += 1
                    count_app += 1
                    count_app_in_work = count_app - count_app_agreed
            person.append([el, count_app, count_app_agreed, count_app_in_work])

    status_order = Case(
        When(status='Approval', then=Value(0)),
        When(status__in=['Revision', 'Primary_contact'], then=Value(1)),
        default=Value(2),
        output_field=IntegerField()
    )

    # Получаем все заявки с сортировкой по кастомному порядку
    applications_sorted = Application.objects.select_related('manage', 'farmer') \
        .annotate(order=status_order) \
        .order_by('order', 'date_delivery')

    applications_data = []
    for app in applications_sorted:
        applications_data.append({
            'id_app': app.id,
            'id_farmer': app.farmer.id,
            'manager': f"{app.manage.user.last_name} {app.manage.user.first_name}",
            'region': getattr(app.farmer, 'region', '—'),  # предполагается, что у фермера есть поле "region"
            'farmer': str(app.farmer),
            'product': app.product or '—',
            'product_quality': app.product_quality or '—',
            'terms_payment': app.terms_payment or '—',
            'date_delivery': app.date_delivery.strftime("%d.%m.%Y") if app.date_delivery else '—',
            'status': app.get_status_display(),
        })

    data = {
        'applications_data': applications_data,
        'data_total_info': data_total_info,
        'person': person,
        'app_approval': Application.objects.filter(status='Approval'),
        'applications_work': applications_work
    }

    return render(req, 'server/index2.html', data)


@login_required
@role_required(['Директор по логистике', 'Директор', 'Менеджер', 'Старший менеджер'])
def show_application(request, pk):
    farmer = get_object_or_404(Farmer, id=pk)
    application = Application.objects.filter(farmer=farmer).first()

    data_farmer_contact = {'phone': [], 'mail': []}
    phone_contacts = FarmerContact.objects.filter(farmer=farmer)
    for contact in phone_contacts:
        formatted_contact = f'{contact.contact} ({contact.get_is_work_display()})'
        if contact.type == 'Phone':
            data_farmer_contact['phone'].append(formatted_contact)
        else:
            data_farmer_contact['mail'].append(formatted_contact)

    is_owner = application and application.manage == request.user.profile

    if farmer.status == 'Free':
        can_edit = True
    else:
        can_edit = is_owner and (application.status not in ['Agreed', 'Not_agreed'])

    history_contacts = HistoryContact.objects.filter(application=application).order_by('-data')
    available_managers = Profile.objects.filter(role=Profile.Role.MANAGER).exclude(id=request.user.profile.id)
    change_manager_form = ChangeManagerForm(application=application)
    form = ApplicationForm(instance=application)
    history_form = HistoryContactForm()
    call_form = CallForm(request.POST)

    if request.method == "POST":
        form_name = request.POST.get("form_name", "")

        # Обработка формы смены менеджера
        if form_name == "change_manager_form" and is_owner:
            change_manager_form = ChangeManagerForm(request.POST, application=application)

            if change_manager_form.is_valid():
                new_manager = change_manager_form.cleaned_data['new_manager']

                if application.manage == new_manager:
                    messages.error(request, "Вы выбрали текущего менеджера. Передача невозможна.")
                    return redirect('application', pk=farmer.id)

                if request.user == new_manager.user:
                    messages.error(request, "Вы не можете передать заявку самому себе.")
                    return redirect('application', pk=farmer.id)

                if ApplicationTransferHistory.objects.filter(application=application, to_user=new_manager.user).exists():
                    messages.error(request, "Эта заявка уже была передана этому менеджеру.")
                    return redirect('application', pk=farmer.id)

                application.manage = new_manager
                application.data_start = date.today()
                application.data_finish = date.today() + timedelta(weeks=3)
                application.save()

                ApplicationTransferHistory.objects.create(
                    application=application,
                    from_user=request.user,
                    to_user=new_manager.user
                )

                messages.success(request, "Менеджер успешно изменен!")
                return redirect('application', pk=farmer.id)
            else:
                messages.error(request, "Ошибка при смене менеджера.")

        # Обработка формы добавления истории созвона
        elif form_name == "history_form" and is_owner:
            history_form = HistoryContactForm(request.POST)
            if history_form.is_valid():
                history_entry = history_form.save(commit=False)
                history_entry.application = application
                history_entry.type = 'Note'

                history_entry.save()
                messages.success(request, "Заметка добавлена!")
                return redirect('application', pk=farmer.id)
            else:
                messages.error(request, "Ошибка при добавлении заметки.")


        elif form_name == "call_form" and is_owner:
            call_form = CallForm(request.POST)
            if call_form.is_valid():
                history_entry = call_form.save(commit=False)
                history_entry.application = application
                history_entry.type = 'Call'
                history_entry.save()
                messages.success(request, "Созвон назначен!")
                return redirect('application', pk=farmer.id)
            else:
                messages.error(request, "Ошибка при назначении созвона.")

        # Обработка формы заявки
        elif can_edit:
            if application and application.status == 'Approval':
                messages.warning(request, "Вы не можете обновить заявку — она находится на согласовании.")
                form = ApplicationForm(instance=application)
                return render(request, 'server/application.html', {
                    'form': form,
                    'application': application,
                    'farmer': farmer,
                    'can_edit': False,
                    'data_farmer_contact': data_farmer_contact,
                    'history_contacts': history_contacts,
                    'history_form': history_form,
                    'call_form': call_form,
                    'change_manager_form': change_manager_form,
                    'is_owner': is_owner,
                    'list_history_manager': ApplicationTransferHistory.objects.filter(application=application)
                })

            form = ApplicationForm(request.POST, instance=application)
            if form.is_valid():
                new_application = form.save(commit=False)
                new_application.farmer = farmer

                if form.cleaned_data['status'] == 'Approval':
                    required_fields = [
                        'inn', 'product', 'product_quality', 'volume', 'point_loading',
                        'price_nds', 'nds', 'terms_payment', 'date_delivery',
                        'daily_loading_rate', 'transport', 'distance', 'price_per_ton'
                    ]
                    missing_fields = [
                        field for field in required_fields
                        if not getattr(new_application, field)
                    ]
                    if missing_fields:
                        messages.error(request, "Нельзя отправить на согласование: не все поля заполнены.")
                        return render(request, 'server/application.html', {
                            'form': form,
                            'application': application,
                            'farmer': farmer,
                            'can_edit': True,
                            'data_farmer_contact': data_farmer_contact,
                            'history_contacts': history_contacts,
                            'history_form': history_form,
                            'call_form': call_form,
                            'change_manager_form': change_manager_form,
                            'is_owner': is_owner,
                            'list_history_manager': ApplicationTransferHistory.objects.filter(application=application)
                        })

                if not application:
                    new_application.manage = request.user.profile
                    new_application.data_start = date.today()
                    new_application.data_finish = date.today() + timedelta(weeks=3)
                    farmer.status = 'Agreed'
                    farmer.save()

                new_application.save()
                messages.success(request, "Заявка успешно сохранена!")
                return redirect('application', pk=farmer.id)
            else:
                print(f"Ошибка: {form.errors.as_json()}")
                messages.error(request, f"Ошибка: {form.errors.as_json()}")

    list_history_manager = [
        [el.from_user, el.to_user, el.transfer_date]
        for el in ApplicationTransferHistory.objects.filter(application=application)
    ]

    context = {
        'farmer': farmer,
        'data_farmer_contact': data_farmer_contact,
        'application': application,
        'form': form,
        'can_edit': can_edit,
        'history_contacts': history_contacts,
        'history_form': history_form,
        'call_form': call_form,
        'change_manager_form': change_manager_form,
        'is_owner': is_owner,
        'list_history_manager': list_history_manager
    }

    return render(request, 'server/application.html', context)

@role_required(['Менеджер', 'Старший менеджер'])
def show_list_call_note(req, pk):
    application = get_object_or_404(Application, id=pk)
    contact_type = req.GET.get('type', 'Call')
    name_page = 'История созвонов' if contact_type == 'Call' else 'История заметок'
    now = django_timezone.now()

    # Разметим вручную поле is_past_call
    history_contacts = HistoryContact.objects.filter(
        application=application,
        type=contact_type
    ).order_by('-data')

    for h in history_contacts:
        h.is_past_call = h.data_call and h.data_call < now

    return render(req, 'server/list_call_note.html', {
        'application': application,
        'history_contacts': history_contacts,
        'type': contact_type,
        'name_page': name_page,
    })

@role_required(['Менеджер', 'Старший менеджер'])
def show_add_application(request):
    if request.method == 'POST':
        form = ApplicationAddForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            # Создание фермера
            farmer = Farmer.objects.create(
                farmer=cd['farmer'],
                full_address=cd.get('full_address'),
                status='Agreed',
            )

            # Контакты
            if cd.get('phone'):
                FarmerContact.objects.create(
                    farmer=farmer,
                    contact=cd['phone'],
                    type='Phone',
                    is_work='work'
                )
            if cd.get('email'):
                FarmerContact.objects.create(
                    farmer=farmer,
                    contact=cd['email'],
                    type='Mail',
                    is_work='work'
                )

            # Создание заявки
            Application.objects.create(
                farmer=farmer,
                manage=request.user.profile,
                status='Not_processed',
                inn=cd.get('inn'),
                product=cd.get('product'),
                product_quality=cd.get('product_quality'),
                price_nds=cd.get('price_nds'),
                nds=cd.get('nds'),
                terms_payment=cd.get('terms_payment'),
                date_delivery=cd.get('date_delivery'),
                daily_loading_rate=cd.get('daily_loading_rate'),
                volume=cd.get('volume'),
                transport=cd.get('transport'),
                distance=cd.get('distance'),
                price_per_ton=cd.get('price_per_ton'),
                point_loading=cd.get('point_loading'),
                data_start=date.today(),
                data_finish=date.today() + timedelta(weeks=3)
            )

            messages.success(request, "Заявка успешно добавлена")
            return redirect('list_application')
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = ApplicationAddForm()
    return render(request, 'server/add_new_application.html', {'form': form})

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@role_required(['Директор по логистике', 'Директор'])
def show_report_admin(req, pk):
    application = get_object_or_404(Application, id=pk)

    # Обработка POST-запроса
    if req.method == 'POST':
        action = req.POST.get('action')

        if action == 'refuse':
            application.status = 'Not_agreed'
            messages.warning(req, "Заявка отклонена.")
        elif action == 'revision':
            application.status = 'Revision'
            messages.info(req, "Заявка отправлена на доработку.")
        elif action == 'approve':
            application.status = 'Agreed'
            messages.success(req, "Заявка утверждена.")
        else:
            messages.error(req, "Неизвестное действие.")

        application.save()
        return redirect('admin_index')  # Замените на ваш URL name


    volume = application.volume or 0
    price_nds = application.price_nds or 0
    nds = application.nds or 0
    transport = application.transport or 0
    distance = application.distance or 0
    price_per_ton = application.price_per_ton or 0

    # Расчёты
    total_with_nds = price_nds * volume
    total_nds = round(price_nds * volume * (1 + nds / 100), 2)
    logistic_price = transport * distance + volume * price_per_ton

    # Расчёты v2
    if application.nds == 0:
        is_nds = False
        sum_result = application.price_nds + application.transport + application.price_per_ton
    else:
        is_nds = True
        sum_result = application.price_nds + (application.price_nds * 0.1) + application.transport + application.price_per_ton

    print(sum_result)
    data_calculation = {
        'total_nds': total_nds,
        'total_with_nds': total_with_nds,
        'nds': total_nds - total_with_nds,
        'logistic_price': logistic_price,
        'result_sum_nds': total_with_nds + logistic_price,
        'result_sum': [total_nds + logistic_price, total_with_nds + logistic_price],
        'sum_result': sum_result,
        'is_nds': is_nds
    }

    data = {
        'el': application,
        'data_calculation': data_calculation,
    }

    return render(req, 'server/report_admin.html', data)

@login_required
@role_required(['Менеджер', 'Старший менеджер'])
def show_list_applications(req):
    application = Application.objects.filter(manage__user__id=req.user.id, status__in=['Approval', 'Primary_contact', 'Revision', 'Not_processed'])

    data = {
        'application': application
    }


    return render(req, 'server/list_application.html', data)


@csrf_exempt
@role_required(['Директор по логистике', 'Директор', 'Старший менеджер'])
def show_person_manage(request):
    if request.method == 'POST':
        manager_id = request.POST.get('manager')
        region_ids = request.POST.getlist('regions')

        if manager_id:
            # Снимаем текущие регионы у менеджера
            Region.objects.filter(manage_id=manager_id).update(manage=None)
            # Привязываем новые
            Region.objects.filter(id__in=region_ids).update(manage_id=manager_id)

        return redirect('person_manage')  # Заменить на актуальное имя

    form = RegionManagerForm(disable_region_field=True)

    data_list_manage = []
    data_manage = []
    data_region = []

    # Все менеджеры
    managers = Profile.objects.filter(role=Profile.Role.MANAGER)

    # Пре-загрузка всех регионов и аграриев (для минимизации запросов)
    regions = Region.objects.select_related('manage').all()
    region_by_manager = defaultdict(list)
    for region in regions:
        if region.manage:
            region_by_manager[region.manage.id].append(region.id)

    # Пре-загрузка всех фермеров по регионам
    farmers = Farmer.objects.select_related('region').all()
    farmers_by_region = defaultdict(list)
    for farmer in farmers:
        if farmer.region:
            farmers_by_region[farmer.region.id].append(farmer.id)

    # Пре-загрузка всех заявок
    applications = Application.objects.select_related('manage', 'farmer').all()

    # Группировка по менеджеру
    for manager in managers:
        manager_data = {
            'manager': manager,
            'region_count': 0,
            'total_farmers': 0,
            'plan': 0,
            'fact': 0,
            'percent': 0,
        }

        # ID регионов менеджера
        manager_region_ids = region_by_manager.get(manager.id, [])
        manager_data['region_count'] = len(manager_region_ids)

        # ID фермеров в этих регионах
        farmer_ids = []
        for region_id in manager_region_ids:
            farmer_ids += farmers_by_region.get(region_id, [])

        manager_data['total_farmers'] = len(farmer_ids)

        # Кол-во заявок по этим фермерам — это план
        plan = [a for a in applications if a.farmer_id in farmer_ids]
        manager_data['plan'] = len(plan)

        # Кол-во заявок со статусом Agreed — это факт
        manager_data['fact'] = len([a for a in plan if a.status == 'Agreed'])

        # Расчет процента
        if manager_data['plan'] > 0:
            manager_data['percent'] = round((manager_data['fact'] / manager_data['plan']) * 100, 2)

        data_manage.append(manager_data)



    # Получаем все регионы с фермерскими и заявочными связями
    regions = Region.objects.prefetch_related(
        'farmer_set__application_set'
    )

    for region in regions:
        farmers = region.farmer_set.all()
        total_farmers = farmers.count()

        # Считаем заявки по всем фермерам региона
        total_applications = 0
        agreed_count = 0
        not_agreed_count = 0

        for farmer in farmers:
            applications = farmer.application_set.all()
            total_applications += applications.count()
            agreed_count += applications.filter(status='Agreed').count()
            not_agreed_count += applications.exclude(status='Agreed').count()

        done_percent = round((agreed_count / total_applications) * 100) if total_applications else 0

        data_region.append({
            'region': region.name,
            'farmers': total_farmers,
            'in_work': not_agreed_count,
            'agreed': agreed_count,
            'percent': done_percent
        })

    data_static_manager = []

    # Менеджеры, участвующие в заявках или регионах
    managers = Profile.objects.filter(
        id__in=Region.objects.exclude(manage=None).values_list('manage_id', flat=True).distinct()
    ).union(
        Profile.objects.filter(id__in=Application.objects.values_list('manage_id', flat=True).distinct())
    )

    for manager in managers:
        applications = Application.objects.filter(manage=manager)
        agreed_apps = applications.filter(status='Agreed')
        app_count = applications.count()
        agreed_count = agreed_apps.count()

        # 1. Среднее количество заявок на регион
        region_count = Region.objects.filter(manage=manager).count() or 1
        avg_app_per_region = round(app_count / region_count, 2)

        # 2. Средний чек
        total_check = agreed_apps.aggregate(
            check_sum=Sum(
                Coalesce(F('price_nds'), 0.0) * Coalesce(F('volume'), 0.0) +
                Coalesce(F('transport'), 0.0),
                output_field=FloatField()
            )
        )['check_sum'] or 0
        avg_check = round(total_check / agreed_count, 2) if agreed_count else 0

        # 3. Среднее время работы заявки
        durations = [
            (a.data_end - a.data_start).days for a in agreed_apps
            if a.data_start and a.data_end and a.data_end > a.data_start
        ]
        avg_days = round(sum(durations) / len(durations), 2) if durations else 0

        # 4. Среднее количество передач заявок
        transfer_count = ApplicationTransferHistory.objects.filter(application__in=applications).count()
        avg_transfers = round(transfer_count / app_count, 2) if app_count else 0

        # 5. Регион с наибольшим количеством закрытых заявок
        top_region_data = agreed_apps.values('farmer__region__name') \
            .annotate(cnt=Count('id')) \
            .order_by('-cnt') \
            .first()
        top_region = top_region_data['farmer__region__name'] if top_region_data else '-'

        # 6. Рейтинг менеджера (по количеству согласованных заявок, можно усложнить)
        rating = agreed_count

        # Добавляем строку в таблицу
        data_static_manager.append({
            'manager': str(manager),
            'avg_applications_per_region': avg_app_per_region,
            'avg_check': avg_check,
            'avg_working_days': avg_days,
            'avg_transfers': avg_transfers,
            'top_region': top_region,
            'rating': rating
        })

    data_static_region = []

    # Получаем все регионы с привязанными менеджерами
    regions = Region.objects.exclude(manage=None)

    for region in regions:
        applications = Application.objects.filter(farmer__region=region)
        agreed_apps = applications.filter(status='Agreed')
        total_applications = applications.count()
        total_agreed = agreed_apps.count()

        # Средний чек по заявкам (по согласованным)
        total_check = agreed_apps.aggregate(
            total=Sum(
                Coalesce(F('price_nds'), 0.0) * Coalesce(F('volume'), 0.0) + Coalesce(F('transport'), 0.0),
                output_field=FloatField()
            )
        )['total'] or 0
        avg_check = round(total_check / total_agreed, 2) if total_agreed else 0

        # Среднее время обработки (по согласованным)
        durations = [
            (a.data_end - a.data_start).days for a in agreed_apps
            if a.data_start and a.data_end and a.data_end > a.data_start
        ]
        avg_processing_time = round(sum(durations) / len(durations), 2) if durations else 0

        # Количество уникальных фермеров в регионе
        total_farmers = Farmer.objects.filter(region=region).distinct().count()

        # Процент успешных заявок
        success_rate = round((total_agreed / total_applications) * 100, 2) if total_applications else 0

        # Назначенный менеджер
        manager = region.manage.get_fio() if hasattr(region.manage, 'get_fio') else str(region.manage)

        # Рейтинг (можно считать местом в рейтинге по кол-ву согласованных заявок)
        # Для упрощения – на этом этапе просто сохраняем общее число, далее отсортируем и присвоим номер
        data_static_region.append({
            'region': region.name,
            'total_app': total_applications,
            'agree_app': total_agreed,
            'avg_check': avg_check,
            'avg_time': avg_processing_time,
            'total_farmer': total_farmers,
            'manager': manager,
            'percent': success_rate,
            'rating': total_agreed
        })

    # Сортируем по количеству согласованных заявок и присваиваем рейтинг
    data_static_region.sort(key=lambda x: x['rating'], reverse=True)
    for idx, entry in enumerate(data_static_region, start=1):
        entry['rating'] = idx

    data = {
        'form': form,
        'manager_count': Profile.objects.filter(role=1).count(),
        'region_count': Region.objects.all().count(),
        'distribution_region_count': Region.objects.exclude(manage=None).count(),
        'application_agreed_count': Application.objects.filter(status='Agreed').count(),
        'managers_regions': {
            manager.id: list(Region.objects.filter(manage=manager).values_list('id', flat=True))
            for manager in Profile.objects.filter(role=Profile.Role.MANAGER)
        },
        'taken_regions': list(Region.objects.exclude(manage=None).values_list('id', flat=True)),
        'all_regions': list(Region.objects.values('id', 'name')),
        'data_manage': data_manage,
        'data_region': data_region,
        'data_static_manager': data_static_manager,
        'data_static_region': data_static_region
    }
    return render(request, 'server/person_manage.html', data)

@role_required(['Директор по логистике', 'Директор', 'Старший менеджер'])
def assign_regions(request):
    if request.method == 'POST':
        manager_id = request.POST.get('manager')
        region_ids = request.POST.getlist('regions[]')

        # Снимаем текущие привязки с выбранного менеджера
        Region.objects.filter(manage_id=manager_id).update(manage=None)

        # Привязываем новые регионы к менеджеру
        Region.objects.filter(id__in=region_ids).update(manage_id=manager_id)

        return redirect('show_person_manage')


def show_notifications(req):
    profile = req.user.profile  # Получаем текущий профиль пользователя

    # Получаем все созвоны по заявкам, где менеджер — текущий пользователь
    call_history = HistoryContact.objects.filter(
        type='Call',
        application__manage=profile,
        data_call__isnull=False
    ).select_related('application__farmer').order_by('-data_call')

    # Формируем структуру вывода
    calls = []
    for call in call_history:
        full_name = call.application.farmer.__str__()  # строковое имя заявки
        short_name = (full_name[:25] + '...') if len(full_name) > 13 else full_name
        calls.append({
            'id_app': call.application.farmer.id,
            'application_name': short_name,
            'dsc': call.dsc,
            'data_call': call.data_call,
        })

    context = {
        'calls': calls
    }

    return render(req, 'server/list_records_call.html', context)


def show_error_403(req):
    user_role = None
    if req.user.is_authenticated:
        try:
            user_role = req.user.profile.role
        except Profile.DoesNotExist:
            pass

    return render(req, 'server/errors-403-error.html', {'user_role': user_role}, status=403)
