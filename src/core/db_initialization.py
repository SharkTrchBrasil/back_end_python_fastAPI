# src/core/db_initialization.py
from sqlalchemy.orm import Session
from src.core import models
from datetime import datetime, timezone # Importe datetime e timezone para timestamps

from src.core.utils.enums import ChatbotMessageGroupEnum


def initialize_roles(db: Session):
    """
    Verifica a existência de roles padrão e as cria se não existirem.
    """
    roles_to_ensure = ['owner', 'manager', 'cashier', 'stockManager']
    existing_roles = db.query(models.Role.machine_name).all()
    existing_roles_names = {role[0] for role in existing_roles} # Converte para set para busca rápida

    new_roles = []
    for role_name in roles_to_ensure:
        if role_name not in existing_roles_names:
            print(f"Role '{role_name}' não encontrada. Criando...")
            new_roles.append(
                models.Role(
                    machine_name=role_name,
                    created_at=datetime.now(timezone.utc), # Use timezone.utc para timestamps consistentes
                    updated_at=datetime.now(timezone.utc)
                )
            )
        else:
            print(f"Role '{role_name}' já existe.")

    if new_roles:
        db.add_all(new_roles)
        db.commit()
        print("Roles padrão criadas/verificadas com sucesso.")
    else:
        print("Todas as roles padrão já existem.")


# ✅ NOVA FUNÇÃO PARA SEMEAR OS TEMPLATES
def seed_chatbot_templates(db: Session):
    """
    Verifica e insere os templates de mensagem do chatbot se eles não existirem.
    """
    templates = [
        # SALES_RECOVERY
        {'message_key': 'abandoned_cart', 'name': 'Carrinho abandonado',
         'message_group': ChatbotMessageGroupEnum.SALES_RECOVERY,
         'default_content': 'Olá 👋 {client.name}\nNotamos que você deixou seu pedido pela metade 🍴🍲\n\nNão perca o que escolheu! Complete sua compra aqui 🛒: {company.url_products}',
         'available_variables': ['client.name', 'company.url_products']},
        {'message_key': 'new_customer_discount', 'name': 'Desconto para novos clientes',
         'message_group': ChatbotMessageGroupEnum.SALES_RECOVERY,
         'default_content': 'Olá, {client.name}! 🎉\n\nJá se passaram alguns dias desde seu primeiro pedido no {company.name}. Queremos te presentear com um desconto exclusivo.\n\nUse o código PRIMEIRA-COMPRA em {company.url_products} e aproveite o seu desconto.\n\nNão perca essa oportunidade! 🎉💸',
         'available_variables': ['client.name', 'company.name', 'company.url_products']},

        # CUSTOMER_QUESTIONS
        {'message_key': 'welcome_message', 'name': 'Mensagem de boas-vindas',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': '👋🏼 Olá, {client.name} \nBem-vindo(a) à {company.name}! Estamos aqui para garantir que sua experiência seja deliciosa e sem complicações. \n\n<b>Como podemos te ajudar hoje?</b> \n\n<b>A.</b> Fazer um pedido 🍽️ \n<b>B.</b> Obter mais informações ℹ \n\nSelecione a letra da opção que você deseja consultar e envie como resposta. Estamos aqui para ajudar!',
         'available_variables': ['client.name', 'company.name']},
        {'message_key': 'absence_message', 'name': 'Mensagem de ausência',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': '👋🏼 Olá, {client.name} \n\nAtualmente estamos fora do nosso horário de atendimento. 🕑 \n\n🕑 <b>Nosso horário de atendimento é:</b> {company.business_hours} \n\nConvidamos você a conferir nosso menu e preparar seu próximo pedido: {company.url_products} \n\nEsperamos vê-lo em breve! 🙌🏼',
         'available_variables': ['client.name', 'company.business_hours', 'company.url_products']},
        {'message_key': 'order_message', 'name': 'Mensagem para fazer um pedido',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'Ótimo! 🎉 Para fazer seu pedido, entre no seguinte link e escolha seus pratos favoritos: \n\n🔗 <b>Faça seu pedido aqui:</b> \n{company.url_products} \n\nEstamos prontos para preparar algo delicioso para você! 🍽️',
         'available_variables': ['company.url_products']},
        {'message_key': 'promotions_message', 'name': 'Mensagem de promoções',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'Grandes notícias 😍🎉 Temos promoções incríveis esperando por você. Aproveite agora e desfrute dos seus pratos favoritos com descontos especiais. 🍕🍔🍣 \n\nNão perca esta oportunidade! Peça hoje e saboreie o irresistível. 🚀🛍️ \n\n🔗 <b>Descubra mais aqui:</b> {company.url_promotions}',
         'available_variables': ['company.url_promotions']},
        {'message_key': 'info_message', 'name': 'Mensagem de informação',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'Claro! \nEncontre todas as informações sobre o nosso restaurante, incluindo horário, serviços de entrega, endereço, custos e mais, no seguinte link: {info.url} 📲',
         'available_variables': ['info.url']},
        {'message_key': 'business_hours_message', 'name': 'Mensagem de horário de funcionamento',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': '⏰ <b>Aqui está nosso horário de atendimento:</b> \n\n{company.business_hours} \n\nEstamos disponíveis durante esses horários para oferecer o melhor em serviço e delícias culinárias. \n\n🔗 <b>Faça seu pedido aqui:</b>{company.url_products}',
         'available_variables': ['company.business_hours', 'company.url_products']},

        # GET_REVIEWS
        {'message_key': 'request_review', 'name': 'Solicitar uma avaliação',
         'message_group': ChatbotMessageGroupEnum.GET_REVIEWS,
         'default_content': 'Oi <b>{client.name}</b>! 👋 \n\nMuito obrigado por escolher o nosso <b>{company.name}</b> \n\nSua opinião é muito importante para nós 🙏 \nVocê pode nos ajudar dando uma avaliação? ⭐ \n\n{order.url} \n\nObrigado, e esperamos vê-lo novamente em breve! 😊',
         'available_variables': ['client.name', 'company.name', 'order.url']},

        # LOYALTY
        {'message_key': 'loyalty_program', 'name': 'Mensagem do Programa de Fidelidade',
         'message_group': ChatbotMessageGroupEnum.LOYALTY,
         'default_content': 'Olá {client.name} 🎉 \n\nEsperamos que tenha gostado da sua última compra! \n\nGraças a ela, você acumulou {client.available_points} pontos, que podem ser trocados por descontos exclusivos 🎊. \n\nExplore seus descontos disponíveis aqui: {company.url_loyalty}. \n\nObrigado por nos escolher!',
         'available_variables': ['client.name', 'client.available_points', 'company.url_loyalty']},

        # ORDER_UPDATES
        {'message_key': 'order_received', 'name': 'Pedido recebido',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '👋 Recebemos o seu pedido Nº {order.public_id}. \n\nEstamos revisando-o. Por favor, aguarde um momento.',
         'available_variables': ['order.public_id']},
        {'message_key': 'order_accepted', 'name': 'Pedido aceito',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '✅ Seu pedido foi aceito! \n\nAcompanhe o progresso do seu pedido Nº {order.public_id} no seguinte link: {order.url}\n\n{client.name}\n{client.number}',
         'available_variables': ['order.public_id', 'order.url', 'client.name', 'client.number']},
        {'message_key': 'order_ready', 'name': 'Pedido pronto', 'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '🙌 Seu pedido Nº {order.public_id} está pronto.',
         'available_variables': ['order.public_id']},
        {'message_key': 'order_on_route', 'name': 'Pedido a caminho',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '🛵 Seu pedido Nº {order.public_id} está a caminho e chegará em breve.',
         'available_variables': ['order.public_id']},
        {'message_key': 'order_arrived', 'name': 'Pedido chegou',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '🎉 Seu pedido Nº {order.public_id} chegou ao destino. Aproveite!',
         'available_variables': ['order.public_id']},
        {'message_key': 'order_delivered', 'name': 'Pedido entregue',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '👏 Tudo certo! Seu pedido Nº {order.public_id} foi entregue. \n\n<b>Esperamos que aproveite!</b>',
         'available_variables': ['order.public_id']},
        {'message_key': 'order_finalized', 'name': 'Pedido finalizado',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '🌟 Obrigado pelo seu pedido Nº {order.public_id}! Tudo saiu perfeito. \n\n<b>Esperamos você em breve em {company.url}!</b>',
         'available_variables': ['order.public_id', 'company.url']},
        {'message_key': 'order_cancelled', 'name': 'Pedido cancelado',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'default_content': '🚫 Lamentamos informar que seu pedido Nº {order.public_id} foi cancelado. \n\nSe tiver alguma dúvida, não hesite em nos contatar.',
         'available_variables': ['order.public_id']}
    ]

    for t_data in templates:
        exists = db.query(models.ChatbotMessageTemplate).filter_by(message_key=t_data['message_key']).first()
        if not exists:
            template = models.ChatbotMessageTemplate(**t_data)
            db.add(template)

    db.commit()