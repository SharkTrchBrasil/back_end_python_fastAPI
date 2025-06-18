import tempfile
import time

from efipay import EfiPay

from src.api.admin.schemas.pix_config import StorePixConfig


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

    # TODO: IMPLEMENTAR PROD
    body = {
        'webhookUrl': 'https://webhook.site/20b9a155-e6f0-4bb8-be5e-9334ab7c8cbc'
    }

    response = efi.pix_config_webhook(params=params, body=body, headers=headers)
    print(response)

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
