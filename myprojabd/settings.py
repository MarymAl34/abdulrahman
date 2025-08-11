from pathlib import Path
from django.utils.translation import gettext_lazy as _

# مسار المشروع الأساسي
BASE_DIR = Path(__file__).resolve().parent.parent

# ⚠️ مفتاح سري للتطوير فقط — غيّره في الإنتاج
SECRET_KEY = 'django-insecure-zwbwtk-o*9ufq3uq3oj@l_sdje0*2w0b=01#v#f-itsodkby+='

# وضع التطوير
DEBUG = True

ALLOWED_HOSTS = []

# التطبيقات
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # التطبيقات المخصصة
    'access',
    'lookup',
    'tickets',
]

# الوسائط (Middleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    # مهم للترجمة وتحديد اللغة من الكوكيز/الهيدر
    'django.middleware.locale.LocaleMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myprojabd.urls'

# القوالب
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # مجلد القوالب العام (اختياري لكن مفيد)
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',   # مهم للترجمة في القوالب
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'myprojabd.wsgi.application'

# قاعدة البيانات (SQLite للتطوير)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# تحقق كلمات المرور
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# الترجمة واللغة
LANGUAGE_CODE = 'ar'                # العربية
TIME_ZONE = 'Asia/Riyadh'           # توقيت الرياض
USE_I18N = True
USE_TZ = True

# اللغات المتاحة (حاليًا عربية فقط – أضف إنجليزي إذا احتجت)
LANGUAGES = [
    ('ar', _('Arabic')),
    # ('en', _('English')),
]

# مسارات ملفات الترجمة (django.po/mo)
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# الملفات الثابتة
STATIC_URL = 'static/'
# (اختياري) مجلد التجميع للإنتاج باستخدام collectstatic
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# (اختياري) مجلدات ثابتة إضافية أثناء التطوير
# STATICFILES_DIRS = [BASE_DIR / 'static']

# الإعداد الافتراضي لمفاتيح الحقول
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
