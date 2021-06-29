"""
Django settings for mobot_web project.

Generated by 'django-admin startproject' using Django 3.2.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import environ
from pathlib import Path
import os


root = environ.Path(__file__) - 3
runtime_env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)
# reading .env file


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = runtime_env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = runtime_env("DEBUG")

DATABASE = runtime_env("DATABASE")

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1').split(',')

# Application definition

INSTALLED_APPS = [
    'django_extensions',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'djmoney',
    'address',
    'djmoney.contrib.exchange',
    'django_fsm',
    'mobot.apps.common.apps.CommonAppConfig',
    'mobot.apps.payment_service.apps.PaymentServiceAppConfig',
    'mobot.apps.merchant_services.apps.MerchantServicesConfig',
    'mobot.apps.mobot_client.apps.MobotClientAppsConfig',
    'mobot.apps.mobot_web.apps.MobotWebConfig'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mobot.apps.mobot_web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mobot.apps.mobot_web.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

if DATABASE == "postgresql":
    DATABASE_NAME = runtime_env("DATABASE_NAME", default="mobot_web")
    DATABASE_USER = runtime_env("DATABASE_USER", default="mobot_web")
    DATABASE_PASSWORD = runtime_env("DATABASE_PASSWORD", default="mobot_web")
    DATABASE_HOST = runtime_env("DATABASE_HOST", default="db")
    DATABASE_PORT = runtime_env("DATABASE_PORT", default=5432)
    DATABASE_SSL_MODE = runtime_env("DATABASE_SSL_MODE", default="prefer")
    DATABASE_SSL_ROOT_CERT = runtime_env("DATABASE_SSL_ROOT_CERT", default="")
    DATABASE_URL = runtime_env.db()

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DATABASE_NAME,
            'USER': DATABASE_USER,
            'PASSWORD': DATABASE_PASSWORD,
            'HOST': DATABASE_HOST,
            'PORT': DATABASE_PORT,
            'OPTIONS': {
                'sslmode': DATABASE_SSL_MODE,
                'sslrootcert': DATABASE_SSL_ROOT_CERT,
            },
        }
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_table',
        }
    }

else:
    # https://docs.microsoft.com/en-us/azure/app-service/configure-custom-container?pivots=container-linux#use-persistent-shared-storage
    DB_ROOT = BASE_DIR if DEBUG else '/home'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(DB_ROOT, 'db.sqlite3'),
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/static'

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
