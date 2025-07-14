from django import forms
from django.contrib.auth.models import User
from .models import *

class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Имя",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "inputFirstName", "placeholder": "Введите свое имя"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "inputLastName", "placeholder": "Введите свою фамилию"}),
    )
    username = forms.CharField(
        label="Логин",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Логин используется при авторизации"}),
    )
    email = forms.EmailField(
        label="Почта",
        widget=forms.EmailInput(attrs={"class": "form-control", "id": "inputEmailAddress", "placeholder": "Почта используется при получении важных уведомлений"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control border-end-0", "id": "inputChoosePassword", "placeholder": "Пароль должен содержать минимум 8 символов"}),
    )
    corp_password = forms.CharField(
        label="Корпоративный пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control border-end-0", "placeholder": "В целях безопасности данных введите корп. пароль компании"}),
    )
    is_senior_manager = forms.BooleanField(
        label="Я старший менеджер",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "flexSwitchCheckChecked"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "password"]

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Этот логин уже существует. Пожалуйста, выберите другой.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if len(password) < 8:
            raise forms.ValidationError("Пароль должен содержать минимум 8 символов.")
        return password


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Логин",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "inputEmailAddress", "placeholder": "Введите свой логин"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control border-end-0", "id": "inputChoosePassword", "placeholder": "Введите свой пароль"}),
    )


class ApplicationForm(forms.ModelForm):
    STATUS_CHOICES = [
        ('Not_processed', 'Не обработан'),
        ('Primary_contact', 'Первичный контакт'),
        ('Refusal', 'Отказ'),
        ('Freezing', 'Заморозка'),
        ('Approval', 'На согласовании'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='Not_processed'
    )

    price_nds = forms.FloatField(required=False)
    nds = forms.IntegerField(required=False)
    transport = forms.IntegerField(required=False)
    distance = forms.IntegerField(required=False)
    price_per_ton = forms.IntegerField(required=False)

    class Meta:
        model = Application
        fields = [
            'inn', 'product', 'product_quality', 'volume', 'point_loading',
            'price_nds', 'nds', 'terms_payment', 'date_delivery',
            'daily_loading_rate', 'transport', 'distance', 'price_per_ton', 'status'
        ]
        widgets = {
            'date_delivery': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'inn': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 12,
                'inputmode': 'numeric',
                'pattern': '\d{1,12}',
                'placeholder': 'Введите ИНН (до 12 цифр)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance

        # По умолчанию статус — "Не обработан"
        if not instance.pk:
            self.fields['status'].initial = 'Not_processed'

        # Отключение всех полей, если заявка на согласовании
        if instance and instance.status == 'Approval':
            for field in self.fields:
                self.fields[field].widget.attrs['disabled'] = True

        # Проверка на заполненность всех обязательных полей для возможности выбора статуса "Approval"
        required_fields = [
            'inn', 'product', 'product_quality', 'volume', 'point_loading',
            'price_nds', 'nds', 'terms_payment', 'date_delivery',
            'daily_loading_rate', 'transport', 'distance', 'price_per_ton'
        ]

        all_filled = all(
            getattr(instance, field) not in [None, '', 0]
            for field in required_fields
        )

        # Если есть незаполненные поля — убираем возможность выбора статуса "Approval"
        if not all_filled:
            self.fields['status'].choices = [
                choice for choice in self.STATUS_CHOICES if choice[0] != 'Approval'
            ]

    def clean_inn(self):
        inn = self.cleaned_data.get('inn')
        if inn:
            if not inn.isdigit():
                raise forms.ValidationError("ИНН должен содержать только цифры.")
            if len(inn) > 12:
                raise forms.ValidationError("ИНН не может содержать более 12 цифр.")
        return inn

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not status:
            raise forms.ValidationError("Необходимо выбрать статус заявки.")
        return status

class HistoryContactForm(forms.ModelForm):
    class Meta:
        model = HistoryContact
        fields = ['dsc']
        widgets = {
            'dsc': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Напишите новую заметку',
                'rows': 3
            }),
        }


class CallForm(forms.ModelForm):
    class Meta:
        model = HistoryContact
        fields = ['data_call', 'dsc']
        widgets = {
            'data_call': forms.TextInput(attrs={
                'class': 'result form-control',
                'id': 'date-time',
                'placeholder': '....-..-.. ..:..',
            }),
            'dsc': forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'inputProductDescription',
                'rows': 3,
                'placeholder': 'Напишите, что хотите обсудить (необязательно)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_call'].required = True

class ChangeManagerForm(forms.ModelForm):
    new_manager = forms.ModelChoiceField(
        queryset=Profile.objects.none(),  # Заполняется в __init__
        label="Выберите менеджера",
        empty_label="Выберите менеджера",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Application
        fields = ['new_manager']

    def __init__(self, *args, **kwargs):
        application = kwargs.pop('application', None)
        super().__init__(*args, **kwargs)

        base_queryset = Profile.objects.filter(role=Profile.Role.MANAGER)

        if application:
            # Получаем user.id менеджеров, которым уже была передана заявка
            already_transferred_to_user_ids = ApplicationTransferHistory.objects.filter(
                application=application
            ).values_list('to_user_id', flat=True)

            # Исключаем текущего менеджера и уже получавших заявку
            self.fields['new_manager'].queryset = base_queryset.exclude(
                user__id__in=list(already_transferred_to_user_ids) + [application.manage.user.id]
            )
        else:
            self.fields['new_manager'].queryset = base_queryset


class ApplicationAddForm(forms.Form):
    farmer = forms.CharField(
        label="Наименование фермера", required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите наименование фермера'})
    )
    full_address = forms.CharField(
        label="Адрес", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите адрес фермера'})
    )
    phone = forms.CharField(
        label="Рабочий телефон", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите телефон фермера'})
    )
    email = forms.EmailField(
        label="Рабочая почта", required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Введите email'})
    )
    inn = forms.CharField(
        label="ИНН", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите ИНН'})
    )
    note = forms.CharField(
        label="Дополнительная информация", required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Введите дополнительную информацию', 'rows': 3})
    )

    product = forms.CharField(
        label="Товар", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите товар'})
    )
    product_quality = forms.CharField(
        label="Качество", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите качество товара'})
    )
    price_nds = forms.FloatField(
        label="Цена СХТП", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите цену с НДС'})
    )
    volume = forms.FloatField(
        label="Объем", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите объем'})
    )
    price_per_ton = forms.IntegerField(
        label="Цена за тн", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите цену за тонну'})
    )
    transport = forms.IntegerField(
        label="Транспорт", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите стоимость транспорта'})
    )
    distance = forms.IntegerField(
        label="Расстояние", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите расстояние'})
    )
    nds = forms.IntegerField(
        label="НДС", required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите НДС'})
    )

    point_loading = forms.CharField(
        label="Адрес погрузки", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите адрес погрузки'})
    )
    date_delivery = forms.DateField(
        label="Срок поставки", required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'type': 'date', 'placeholder': 'Выберите дату'
        })
    )
    daily_loading_rate = forms.CharField(
        label="Суточная норма погрузки", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите суточную норму'})
    )
    terms_payment = forms.CharField(
        label="Условия оплаты", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите условия оплаты'})
    )

    def clean(self):
        cleaned_data = super().clean()
        required_numbers = ['price_nds', 'volume', 'transport', 'distance', 'price_per_ton']
        for field in required_numbers:
            val = cleaned_data.get(field)
            if val is not None and not isinstance(val, (int, float)):
                self.add_error(field, "Поле должно быть числовым")


class RegionManagerForm(forms.Form):
    manager = forms.ModelChoiceField(
        queryset=Profile.objects.filter(role=Profile.Role.MANAGER),
        label='Менеджер',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'manager-select'})
    )
    regions = forms.ModelMultipleChoiceField(
        queryset=Region.objects.all(),
        label='Регионы',
        widget=forms.SelectMultiple(attrs={'class': 'single-select', 'id': 'region-select'})
    )

    def __init__(self, *args, **kwargs):
        disabled = kwargs.pop('disable_region_field', False)
        super().__init__(*args, **kwargs)
        if disabled:
            self.fields['regions'].widget.attrs['disabled'] = 'disabled'