
# Imports da biblioteca padrão do Python
import os
from pathlib import Path

# Imports de bibliotecas de terceiros (instaladas com pip)
import dj_database_url
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
# É importante que isso aconteça antes do código usar as variáveis
load_dotenv()



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/how-to/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-q^ahp+(y(40dg1ej7ue@84t9fb$a-s%in$p6v8dcx=if&_6#gj'
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'



ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost,http://127.0.0.1').split(',')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'core',
    'django.contrib.humanize',
    'mathfilters',
    'notas_fiscais',
    'storages',
    'pdv',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.BPOManagementMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'setup.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.global_announcement',
                'accounts.context_processors.employee_context',
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

WSGI_APPLICATION = 'setup.wsgi.application'



# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
if 'DATABASE_URL' in os.environ and 'sqlite' not in os.environ.get('DATABASE_URL'):
    # Esta parte só será executada no Render (pois a URL será 'postgres://...')
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600)
    }
else:
    # Esta parte será executada no seu PC (pois a URL é 'sqlite://...')
    # ou se a variável não for encontrada.
    print("### AVISO: Usando banco de dados SQLite local para desenvolvimento. ###")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_L10N = True

USE_TZ = True

USE_THOUSAND_SEPARATOR = True

NUMBER_GROUPING = 3
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/how-to/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files (Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login URL for authentication
LOGIN_URL = 'login'

LOGIN_REDIRECT_URL = 'smart_redirect'

# ==================================================================
#  CONFIGURAÇÃO DE MÍDIA - AMAZON S3 (Padrão Django 5.x)
# ==================================================================

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')

if AWS_STORAGE_BUCKET_NAME:
    # Configurações Gerais do S3
    AWS_S3_REGION_NAME = 'us-east-2'
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_VERIFY = True
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    
    # --- AQUI ESTÁ A MUDANÇA CRUCIAL ---
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "location": "media", # Força a pasta media
                "default_acl": None, # Corrige o erro de permissão
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    
    # URLs
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

else:
    # Fallback para desenvolvimento local sem S3
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }




# ==================================================================
#  CONFIGURAÇÕES DA API DE NOTAS FISCAIS (FOCUS NF-e)
# ==================================================================

# Captura o token do arquivo .env (no seu PC) ou das Variáveis de Ambiente (no Render)
NFE_TOKEN_HOMOLOGACAO = os.environ.get('NFE_TOKEN_HOMOLOGACAO')

# Já deixamos preparado para quando você for para produção no futuro
NFE_TOKEN_PRODUCAO = os.environ.get('NFE_TOKEN_PRODUCAO')

# Configuração da URL da API Focus NFe
if DEBUG:
    FOCUS_API_URL = os.environ.get('FOCUS_API_URL', 'https://homologacao.focusnfe.com.br')
else:
    FOCUS_API_URL = os.environ.get('FOCUS_API_URL', 'https://api.focusnfe.com.br')


# Configurações Banco Inter
INTER_CLIENT_ID = os.environ.get('INTER_CLIENT_ID')
INTER_CLIENT_SECRET = os.environ.get('INTER_CLIENT_SECRET')

# MUDANÇA AQUI: Adicionamos 'certs' dentro do join para o Python usar a barra correta (\ ou /)
INTER_CERT_CRT = os.path.join(BASE_DIR, 'certs', os.environ.get('INTER_CERT_CRT', 'inter.crt'))
INTER_CERT_KEY = os.path.join(BASE_DIR, 'certs', os.environ.get('INTER_CERT_KEY', 'inter.key'))


# ==================================================================
#  CONFIGURAÇÃO STRIPE (PAGAMENTOS)
# ==================================================================

import os

# Chaves de API (Lê do ambiente ou usa string vazia se não achar)
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')

# Webhook Secret (IMPORTANTE: Voltar para os.environ)
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# URL do domínio (Dinâmico)
DOMAIN_URL = os.environ.get('DOMAIN_URL', 'http://127.0.0.1:8000')

# SEUS PLANOS (Esses podem ficar aqui pois são fixos, a não ser que mude os preços)
STRIPE_PRICE_IDS = {
    'financeiro': 'price_1SdviECzwuU2PN4ZsmrpsTME', # Plano Gestão Financeira
    'completo':   'price_1Sdvj1CzwuU2PN4ZTnbyeWBH', # Plano Gestão Total
}


# Adicione isso para garantir que o Django entenda que está rodando em HTTPS no Render
# Sem isso, você pode ter erros de "CSRF Failed" ao tentar logar vindo da Landing Page.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

