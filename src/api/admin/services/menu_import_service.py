import google.generativeai as genai
import json
import os
from typing import List, Dict
from sqlalchemy.orm import Session
import logging

from src.api.schemas.products.category import CategoryCreate
from src.api.schemas.products.product import SimpleProductWizardCreate
from src.api.schemas.products.product_category_link import ProductCategoryLinkCreate

# Seus CRUDs exatos
from src.api.crud import crud_category, crud_product, store_crud
from src.core import models

# É uma boa prática usar logging
logger = logging.getLogger(__name__)

# Carrega a API Key do ambiente (Railway)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


async def process_menu_with_gemini(db: Session, store_id: int, file_data_list: List[Dict]):
    """
    Tarefa de background que usa a IA do Gemini e os CRUDs do projeto para criar o cardápio.
    """
    if not GEMINI_API_KEY:
        logger.error(f"GEMINI_API_KEY não configurada para store_id: {store_id}. A importação foi abortada.")
        # Futuramente: notificar o usuário do erro de configuração via WebSocket.
        return

    # 1. Preparar o prompt para a IA (AGORA ALINHADO COM SEUS SCHEMAS)
    # Pedimos o preço como um número para facilitar a conversão para centavos.
    prompt_text = """
    Analise as imagens do cardápio em anexo. Sua tarefa é extrair todas as categorias e os produtos dentro de cada uma.
    Retorne a resposta EXCLUSIVAMENTE em formato JSON, seguindo esta estrutura rigorosa:
    {
      "categories": [
        {
          "name": "Pizzas Tradicionais",
          "products": [
            {
              "name": "Pizza de Mussarela",
              "description": "Molho de tomate fresco, queijo mussarela e orégano.",
              "price": 49.90
            },
            {
              "name": "Pizza Calabresa",
              "description": "Molho, mussarela, calabresa fatiada e cebola.",
              "price": 52.00
            }
          ]
        },
        {
          "name": "Bebidas",
          "products": [
            {
              "name": "Coca-Cola 2L",
              "description": null,
              "price": 12.50
            }
          ]
        }
      ]
    }
    Se um produto não tiver descrição, use null. Se não conseguir identificar o preço, use 0.0.
    Não inclua nenhuma observação ou texto fora do objeto JSON.
    """

    image_parts = [{"mime_type": file_data["content_type"], "data": file_data["content"]} for file_data in
                   file_data_list]

    # 2. Chamar a API do Gemini Pro Vision
    try:
        model = genai.GenerativeModel('gemini-pro-vision')
        response = await model.generate_content_async([prompt_text, *image_parts])

        json_response_str = response.text
        if "```json" in json_response_str:
            json_response_str = json_response_str.split("```json")[1].split("```")[0].strip()

        menu_data = json.loads(json_response_str)
        logger.info(f"✅ Resposta da IA para store_id {store_id} recebida e parseada com sucesso.")

    except Exception as e:
        logger.error(f"🚨 Erro ao processar com Gemini Vision para store_id {store_id}: {e}")
        # Futuramente: notificar o usuário.
        return

    # 3. Salvar os dados no banco de dados USANDO SEUS CRUDS
    try:
        logger.info(f"Iniciando gravação no banco de dados para store_id {store_id}...")
        for cat_data in menu_data.get("categories", []):
            category_name = cat_data.get("name")
            if not category_name or not isinstance(category_name, str) or len(category_name.strip()) == 0:
                continue

            # Cria a categoria usando seu CRUD
            category_schema = CategoryCreate(name=category_name.strip(), type='GENERAL', is_active=True)
            # A função create_category que você me deu já faz commit, então vamos chamá-la por último.
            # Por enquanto, vamos apenas criar o objeto sem commitar.
            max_priority_cat = db.query(models.func.max(models.Category.priority)).filter(
                models.Category.store_id == store_id).scalar() or 0
            db_category = models.Category(**category_schema.model_dump(), store_id=store_id,
                                          priority=max_priority_cat + 1)
            db.add(db_category)
            db.flush()  # Para obter o ID da categoria

            logger.info(f"  - Categoria preparada: '{db_category.name}' (ID provisório: {db_category.id})")

            for prod_data in cat_data.get("products", []):
                product_name = prod_data.get("name")
                if not product_name or not isinstance(product_name, str) or len(product_name.strip()) == 0:
                    continue

                # Converte o preço para centavos, como seu sistema espera
                price_in_cents = int(float(prod_data.get("price", 0.0)) * 100)

                # Monta o schema de criação do link com a categoria e o preço
                link_data = ProductCategoryLinkCreate(category_id=db_category.id, price=price_in_cents,
                                                      is_available=True)

                # Monta o schema de criação do produto (SimpleProductWizardCreate)
                # Este schema é perfeito para a situação.
                product_schema = SimpleProductWizardCreate(
                    name=product_name.strip(),
                    description=prod_data.get("description"),
                    product_type='INDIVIDUAL',
                    status='ACTIVE',
                    category_links=[link_data]
                )

                # Prepara o objeto do produto para ser salvo
                product_dict = product_schema.model_dump(exclude={'category_links'})
                max_priority_prod = db.query(models.func.max(models.Product.priority)).filter(
                    models.Product.store_id == store_id).scalar() or 0
                db_product = models.Product(**product_dict, store_id=store_id, priority=max_priority_prod + 1)
                db.add(db_product)
                db.flush()  # Para obter o ID do produto

                # Adiciona o link da categoria ao produto
                db_link = models.ProductCategoryLink(product_id=db_product.id, **link_data.model_dump())
                db.add(db_link)

                logger.info(f"    - Produto preparado: '{db_product.name}' (Preço: {price_in_cents} centavos)")

        # Agora sim, fazemos um único commit para salvar tudo
        db.commit()
        logger.info(f"✅ Cardápio para store_id {store_id} importado e salvo no banco com sucesso!")

        # Futuramente: Disparar evento de atualização para a UI
        # from src.api.admin.utils.emit_updates import emit_updates_products
        # await emit_updates_products(db, store_id)

    except Exception as e:
        db.rollback()
        logger.error(f"🚨 Erro ao salvar dados no banco para store_id {store_id}: {e}", exc_info=True)
        # Futuramente: notificar o usuário.