# Em: src/api/services/verification_service.py
import asyncio

from sqlalchemy.orm import Session
from src.core import models
from src.core.utils.enums import StoreVerificationStatus

class VerificationService:
    """
    Orquestra o processo de verificação de uma nova loja e seu responsável.
    """
    def __init__(self, db: Session):
        self.db = db

    async def start_verification_process(self, store: models.Store, user: models.User):
        """
        Método principal que inicia e gerencia todas as etapas de verificação.
        """
        print(f"🚀 Iniciando processo de verificação para a loja ID: {store.id} e usuário ID: {user.id}")

        # Etapa 1: Mudar o status para indicar que a verificação começou
        store.verification_status = StoreVerificationStatus.PENDING
        self.db.add(store)
        self.db.commit()

        # Etapa 2: Validar os documentos (CPF e CNPJ)
        # Por enquanto, vamos simular uma verificação bem-sucedida.
        # No futuro, aqui entraria a chamada para uma API da Receita Federal, por exemplo.
        cnpj_valid = await self._verify_document(store.cnpj, "CNPJ")
        cpf_valid = await self._verify_document(user.cpf, "CPF")

        if not cnpj_valid or not cpf_valid:
            print(f"❌ Verificação de documentos falhou para a loja {store.id}.")
            store.verification_status = StoreVerificationStatus.REJECTED
            store.internal_notes = "Documento (CPF ou CNPJ) inválido."
            self.db.commit()
            return

        # Etapa 3: Enviar e-mail de verificação
        # (Vamos adicionar a lógica de envio de e-mail no próximo passo)
        await self._send_verification_email(user)

        # Etapa 4 (Opcional): Se tudo até aqui for automático, podemos aprovar.
        # Ou manter como PENDING para uma revisão manual.
        # store.verification_status = StoreVerificationStatus.VERIFIED
        # self.db.commit()

        print(f"✅ Processo de verificação para a loja {store.id} em andamento.")

    async def _verify_document(self, document: str | None, doc_type: str) -> bool:
        """
        Simula a verificação de um documento (CPF ou CNPJ).
        """
        if not document:
            print(f"AVISO: Documento do tipo {doc_type} não fornecido. Pulando verificação.")
            return True # Ou False, se o documento for obrigatório

        print(f"🔎 Verificando {doc_type}: {document}...")
        # LÓGICA DE SIMULAÇÃO:
        # No mundo real, aqui você chamaria uma API externa.
        # Ex: response = await client.get(f"https://api.receita.gov.br/v1/{doc_type}/{document}")
        # if response.status_code != 200: return False
        await asyncio.sleep(2) # Simula a demora da chamada de rede
        print(f"👍 Documento {doc_type} {document} parece válido.")
        return True

    async def _send_verification_email(self, user: models.User):
        """
        Simula o envio de um e-mail de verificação.
        """
        print(f"✉️ Enviando e-mail de verificação para {user.email}...")
        # LÓGICA DE ENVIO DE E-MAIL:
        # Aqui você usaria uma biblioteca como 'fastapi-mail' para enviar um
        # e-mail com um link de confirmação.
        # Ex: await fm.send_message(...)
        await asyncio.sleep(1)
        print(f"✅ E-mail enviado para {user.email}.")