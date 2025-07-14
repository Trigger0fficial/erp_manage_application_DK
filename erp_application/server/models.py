from django.contrib.auth.models import User
from django.db import models


class CorpPassword(models.Model):
    class Meta:
        verbose_name = 'Корпоративный пароль'
        verbose_name_plural = 'Корпоративные пароли'

    date = models.DateTimeField(verbose_name='Дата создания')
    manage = models.CharField(verbose_name='Пароль для менеджера', max_length=30)
    total_manage = models.CharField(verbose_name='Пароль для старшего менеджера', max_length=30)

class Profile(models.Model):
    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
    class Role(models.IntegerChoices):
        MANAGER = 1, 'Менеджер'
        DIRECTOR = 2, 'Директор'
        LOGISTICS_DIRECTOR = 3, 'Директор по логистике'
        SALES_DIRECTOR = 4, 'Старший менеджер'

    user = models.OneToOneField(User, verbose_name='Пользователь',  on_delete=models.PROTECT)
    role = models.IntegerField(verbose_name='Роль', choices=Role.choices)
    plan_work = models.CharField(verbose_name='План работ', max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.get_role_display()})"


class Farmer(models.Model):
    class Meta:
        verbose_name = 'Фермер'
        verbose_name_plural = 'Фермеры'


    full_address = models.CharField(verbose_name='Адресс', max_length=5000, blank=True, null=True)
    farmer = models.CharField(verbose_name='Фермер', max_length=1000, blank=True, null=True)
    status = models.CharField(verbose_name='Статус', choices=[('Free', 'Свободный'),
                                                              ('Not_contact', 'Нет контакта'),
                                                              ('Agreed', 'Создана заявка'),], max_length=40)
    region = models.ForeignKey('Region', verbose_name='Регион', blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.farmer}"


class FarmerContact(models.Model):
    class Meta:
        verbose_name = 'Контакт фермера'
        verbose_name_plural = 'Контакты фермеров'

    type = models.CharField(verbose_name='Тип', choices=[('Phone', 'Телефон'), ('Mail', 'Почта')], default='Phone', max_length=155)
    contact = models.CharField(verbose_name='Контакт', max_length=1000)
    is_work = models.CharField(verbose_name='Рабочий?', choices=[('work', 'Рабочий'),
                                                                 ('not_work', 'Не рабочий'),
                                                                 ('undefined', 'Не определен')],
                               default='undefined', max_length=40)
    farmer = models.ForeignKey(Farmer, verbose_name='Заявка', on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.get_type_display()}: {self.contact} ({self.get_is_work_display()})"


class Application(models.Model):
    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'

    STATUS_CHOICES = [
        ('Not_processed', 'Не обработан'),
        ('Primary_contact', 'Первичный контакт'),
        ('Refusal', 'Отказ'),
        ('Freezing', 'Заморозка'),
        ('Approval', 'На согласовании'),
        ('Agreed', 'Согласовано'),
        ('Not_agreed', 'Не согласовано'),
        ('Revision', 'Отправлен на доработку'),
    ]

    manage = models.ForeignKey(Profile, verbose_name='Менеджер', on_delete=models.CASCADE)
    farmer = models.ForeignKey(Farmer, verbose_name='Фермер', on_delete=models.CASCADE)
    status = models.CharField(verbose_name='Статус', choices=STATUS_CHOICES, max_length=40, default='Not_processed')
    inn = models.CharField(verbose_name='ИНН', max_length=12, blank=True, null=True)
    product = models.CharField(verbose_name='Товар', max_length=155, blank=True, null=True)
    point_loading = models.CharField(verbose_name='Точка выгрузки', max_length=255, blank=True, null=True)
    product_quality = models.CharField(verbose_name='Качество товара', max_length=255, blank=True, null=True)
    price_nds = models.FloatField(verbose_name='Цена СХТП', blank=True, null=True, default=0)
    nds = models.IntegerField(verbose_name='НДС', blank=True, null=True, default=0)
    terms_payment = models.CharField(verbose_name='Условия оплаты', max_length=155, blank=True, null=True)
    date_delivery = models.DateField(verbose_name='Срок поставки', blank=True, null=True)
    daily_loading_rate = models.CharField(verbose_name='Суточная норма погрузки', max_length=255, blank=True, null=True)
    volume = models.FloatField(verbose_name='Объем', max_length=255, blank=True, null=True)
    transport = models.IntegerField(verbose_name='Транспорт', blank=True, null=True, default=0)
    distance = models.IntegerField(verbose_name='Расстояние', blank=True, null=True, default=0)
    price_per_ton = models.IntegerField(verbose_name='Цена за тн', blank=True, null=True, default=0)
    data_start = models.DateField(verbose_name='Дата начала', blank=True, null=True)
    data_end = models.DateField(verbose_name='Дата завершения', blank=True, null=True)
    data_finish = models.DateField(verbose_name='Дата дедлайна', blank=True, null=True)

    def __str__(self):
        return f"Заявка #{self.id} - {self.farmer.farmer} ({self.get_status_display()})"


class Region(models.Model):
    class Meta:
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'

    name = models.CharField(verbose_name='Наименование региона', max_length=500)
    manage = models.ForeignKey(Profile, verbose_name='Менеджер', blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return  f'{self.name} - {self.manage}'

class ApplicationTransferHistory(models.Model):
    class Meta:
        verbose_name = 'История передачи заявки'
        verbose_name_plural = 'Истории передачи заявок'

    application = models.ForeignKey(Application, verbose_name='Заявка', on_delete=models.CASCADE)
    transfer_date = models.DateTimeField(verbose_name='Дата передачи', auto_now_add=True)
    from_user = models.ForeignKey(User, related_name='transfers_from', verbose_name='Кто передает', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='transfers_to', verbose_name='Кому передает', on_delete=models.CASCADE)

    def __str__(self):
        return f"Заявка #{self.application.id} передана от {self.from_user.username} к {self.to_user.username} ({self.transfer_date})"


class HistoryContact(models.Model):
    class Meta:
        verbose_name = 'История созвона'
        verbose_name_plural = 'История созвонов'

    type = models.CharField(verbose_name='Тип', choices=[('Call', 'Звонок'),
                                                         ('Note', 'Примечание'),
                                                         ('Notification', 'Уведомление')], max_length=20, default='Call',
                            null=True, blank=True)
    data = models.DateTimeField(verbose_name='Дата', auto_now_add=True)
    dsc = models.TextField(verbose_name='Примечание')
    application = models.ForeignKey(Application, verbose_name='Заявка', on_delete=models.PROTECT)
    data_call = models.DateTimeField(verbose_name='Дата созвона', null=True, blank=True)

    def __str__(self):
        return f"История {self.application.id} от {self.data.strftime('%Y-%m-%d %H:%M')}"




