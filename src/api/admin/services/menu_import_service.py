import openai
import json
import os
import base64
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from src.api.schemas.products.category import CategoryCreate
from src.api.schemas.products.product import SimpleProductWizardCreate
from src.api.schemas.products.product_category_link import ProductCategoryLinkCreate
from src.core import models

logger = logging.getLogger(__name__)

# Carrega a API Key da OpenAI do ambiente (Railway)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY:
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


async def process_menu_with_openai(db: Session, store_id: int, user_id: int, file_data_list: List[Dict]):
    """
    Tarefa de background que usa a IA da OpenAI (GPT-4 Vision) para criar o cardápio.
    """
    if not client:
        logger.error(f"OPENAI_API_KEY não configurada para store_id: {store_id}. A importação foi abortada.")
        return

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
            }
          ]
        }
      ]
    }
    Se um produto não tiver descrição, use null. Se não conseguir identificar o preço, use 0.0.
    Não inclua nenhuma observação ou texto fora do objeto JSON.
    """

    image_messages = []
    for file_data in file_data_list:
        base64_image = base64.b64encode(file_data["content"]).decode('utf-8')
        image_messages.append({
            "type": "image_url",
            "image_url": {"url": f"data:{file_data['content_type']};base64,{base64_image}"}
        })

    try:
        logger.info(f"Enviando requisição para a API da OpenAI para store_id {store_id}...")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt_text}, *image_messages]
                }
            ],
            max_tokens=4000,
        )

        json_response_str = response.choices[0].message.content
        if "```json" in json_response_str:
            json_response_str = json_response_str.split("```json")[1].split("```")[0].strip()

        menu_data = json.loads(json_response_str)
        logger.info(f"✅ Resposta da OpenAI para store_id {store_id} recebida e parseada com sucesso.")

    except Exception as e:
        logger.error(f"🚨 Erro ao processar com OpenAI Vision para store_id {store_id}: {e}", exc_info=True)
        return

    try:
        logger.info(f"Iniciando gravação no banco de dados para store_id {store_id}...")
        for cat_data in menu_data.get("categories", []):
            category_name = cat_data.get("name")
            if not category_name or not isinstance(category_name, str) or len(category_name.strip()) == 0:
                continue

            category_schema = CategoryCreate(name=category_name.strip(), type='GENERAL', is_active=True)
            max_priority_cat = db.query(func.max(models.Category.priority)).filter(
                models.Category.store_id == store_id).scalar() or 0
            db_category = models.Category(**category_schema.model_dump(exclude={'option_groups', 'schedules'}),
                                          store_id=store_id, priority=max_priority_cat + 1)
            db.add(db_category)
            db.flush()
            logger.info(f"  - Categoria preparada: '{db_category.name}' (ID provisório: {db_category.id})")

            for prod_data in cat_data.get("products", []):
                product_name = prod_data.get("name")
                if not product_name or not isinstance(product_name, str) or len(product_name.strip()) == 0:
                    continue

                price_in_cents = int(float(prod_data.get("price", 0.0)) * 100)
                link_data = ProductCategoryLinkCreate(category_id=db_category.id, price=price_in_cents,
                                                      is_available=True)
                product_schema = SimpleProductWizardCreate(
                    name=product_name.strip(),
                    description=prod_data.get("description"),
                    product_type='INDIVIDUAL',
                    status='ACTIVE',
                    category_links=[link_data]
                )

                product_dict = product_schema.model_dump(exclude={'category_links', 'variant_links'})
                max_priority_prod = db.query(func.max(models.Product.priority)).filter(
                    models.Product.store_id == store_id).scalar() or 0
                db_product = models.Product(**product_dict, store_id=store_id, priority=max_priority_prod + 1)
                db.add(db_product)
                db.flush()

                db_link = models.ProductCategoryLink(product_id=db_product.id, **link_data.model_dump())
                db.add(db_link)
                logger.info(f"    - Produto preparado: '{db_product.name}' (Preço: {price_in_cents} centavos)")

        db.commit()
        logger.info(f"✅ Cardápio para store_id {store_id} importado via OpenAI e salvo com sucesso!")

    except Exception as e:
        db.rollback()
        logger.error(f"🚨 Erro ao salvar dados no banco para store_id {store_id}: {e}", exc_info=True)