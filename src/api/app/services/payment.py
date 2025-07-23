import tempfile
import time

from efipay import EfiPay

from src.api.admin.schemas.pix_config import StorePixConfig
from src.core.config import config


def get_efi_pay(pix_config):
    with tempfile.NamedTemporaryFile(delete=False) as temp_certificate:
        temp_certificate.write(pix_config.certificate)
        temp_certificate.flush()

        credentials = {
            'client_id': pix_config.client_id,
            'client_secret': pix_config.client_secret,
            'sandbox': True,
            'certificate': temp_certificate.name
        }

        efi = EfiPay(credentials)

        return efi


def get_master_efi_pay():
    credentials = {
        'client_id': config.MASTER_CLIENT_ID,
        'client_secret':  config.MASTER_CLIENT_SECRET,
        'sandbox': config.MASTER_SANDBOX,
        'certificate': '',
    }

    return EfiPay(credentials)


def create_webhook(
    store_id: int,
    pix_config: StorePixConfig,
    hmac_key: str,
):
    efi = get_efi_pay(pix_config)

    headers = {
        'x-skip-mtls-checking': 'true'
    }

    params = {
        'chave': pix_config.pix_key
    }

    # A URL do seu backend + a rota específica para webhooks de PIX
    webhook_url_pix = "https://api-pdvix-production.up.railway.app/webhook/pix"

    body = {
        'webhookUrl': webhook_url_pix
    }

    response = efi.pix_config_webhook(params=params, body=body, headers=headers)

    print('WEBHOOK RESPONSE', response)

    return response

def get_webhook(pix_config):
    efi = get_efi_pay(pix_config)

    params = {
        'chave': pix_config.pix_key
    }

    response = efi.pix_detail_webhook(params=params)

    return response

def create_charge(pix_config, amount, cpf, name):
    efi = get_efi_pay(pix_config)

    body = {
        'calendario': {
            'expiracao': 10 * 60
        },
        'devedor': {
            'cpf': cpf,
            'nome': name
        },
        'valor': {
            'original': "{:.2f}".format(amount / 100)
        },
        'chave': pix_config.pix_key
    }

    return efi.pix_create_immediate_charge(body=body)


def pix_devolution(pix_config, e2eid, amount):
    efi = get_efi_pay(pix_config)

    params = {
        'e2eId': e2eid,
        'id': round(time.time() * 1000)
    }

    body = {
        'valor': "{:.2f}".format(amount / 100)
    }

    return efi.pix_devolution(params=params, body=body)


def resend_events(pix_config, e2eids):
    efi = get_efi_pay(pix_config)

    body = {
        "tipo": "PIX_RECEBIDO",  # PIX_RECEBIDO, PIX_ENVIADO, DEVOLUCAO_RECEBIDA, DEVOLUCAO_ENVIADA
        "e2eids": e2eids
    }

    return efi.pix_resend_webhook(body=body)


def list_plans(name):
    efi = get_master_efi_pay()

    body = {
        'limit': 100,
        'offset': 0,
        'name': name
    }

    result = efi.list_plans(body=body)
    print('RESULT PLANS', result)
    return result['data']


def create_plan(name, repeats, interval):
    efi = get_master_efi_pay()

    body = {
        'name': name,
        'repeats': repeats,
        'interval': interval
    }

    result = efi.create_plan(body=body)
    return result['data']


def create_subscription(efi_plan_id, plan, payment_token, customer, address):
    efi = get_master_efi_pay()


    # A URL do seu backend + a rota específica para webhooks de assinaturas
    notification_url_subscriptions = "https://api-pdvix-production.up.railway.app/webhook/subscriptions"

    params = {
        'id': efi_plan_id
    }

    body = {
        'items': [
            {
                'name': plan.plan_name,
                'value': plan.price,
                'amount': 1
            }
        ],
        'metadata': {
            'notification_url': notification_url_subscriptions
        },
        'payment': {
            'credit_card': {
                'payment_token': payment_token,
                'billing_address': address.dict(),
                'customer': customer.dict()
            }
        }
    }

    result = efi.create_one_step_subscription(params=params, body=body)
    print('RESULT', result)
    return result['data']


def cancel_subscription(subscription_id):
    efi = get_master_efi_pay()

    params = {
        'id': subscription_id
    }

    return efi.cancel_subscription(params=params)


def get_notification(token):
    efi = get_master_efi_pay()

    params = {
        'token': token
    }

    result = efi.get_notification(params=params)
    return result['data']
