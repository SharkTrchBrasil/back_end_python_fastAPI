import tempfile

from efipay import EfiPay

from src.api.admin.schemas.pix_config import StorePixConfig


def create_webhook(
    store_id: int,
    pix_config: StorePixConfig,
    hmac_key: str,
):
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

        params = {
            'chave': pix_config.pix_key
        }

        response = efi.pix_detail_webhook(params=params)

        return response