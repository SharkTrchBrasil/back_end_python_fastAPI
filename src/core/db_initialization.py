# Arquivo: src/core/db_initialization.py

from decimal import Decimal
from sqlalchemy.orm import Session
from src.core import models
from datetime import datetime, timezone
from src.core.utils.enums import ChatbotMessageGroupEnum

def initialize_roles(db: Session):
    """
    Verifica a existência de roles padrão e as cria se não existirem.
    """
    roles_to_ensure = ['owner', 'manager', 'cashier', 'stockManager']
    existing_roles = db.query(models.Role.machine_name).all()
    existing_roles_names = {role[0] for role in existing_roles}

    new_roles = []
    for role_name in roles_to_ensure:
        if role_name not in existing_roles_names:
            print(f"Role '{role_name}' não encontrada. Criando...")
            new_roles.append(
                models.Role(
                    machine_name=role_name,
                    created_at=datetime.now(timezone.utc),
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

def seed_plans_and_features(db: Session):
    """
    Define nossa estrutura de valor único
    """
    print("Iniciando a semeadura da estrutura de Planos e Features...")

    # Features essenciais
    features_data = [
        {'feature_key': 'review_automation', 'name': 'Automação de Avaliações',
         'description': 'Solicita avaliações dos clientes automaticamente após a entrega.', 'is_addon': False},
        {'feature_key': 'auto_printing', 'name': 'Impressão Automática',
         'description': 'Configure a impressão automática de pedidos assim que são recebidos.', 'is_addon': False},
        {'feature_key': 'basic_reports', 'name': 'Relatórios Básicos',
         'description': 'Visualize o desempenho de suas vendas com relatórios essenciais.', 'is_addon': False},
        {'feature_key': 'coupons', 'name': 'Módulo de Promoções',
         'description': 'Crie cupons de desconto para atrair e fidelizar clientes.', 'is_addon': False},
        {'feature_key': 'inventory_control', 'name': 'Controle de Estoque',
         'description': 'Gerencie a quantidade de produtos disponíveis em tempo real.', 'is_addon': False},
        {'feature_key': 'pdv', 'name': 'Ponto de Venda (PDV)',
         'description': 'Sistema completo para registrar vendas no balcão.', 'is_addon': False},
        {'feature_key': 'totem', 'name': 'Módulo de Totem',
         'description': 'Permita que seus clientes façam pedidos sozinhos através de um totem de autoatendimento.',
         'is_addon': False},
        {'feature_key': 'multi_device_access', 'name': 'Acesso em Múltiplos Dispositivos',
         'description': 'Gerencie sua loja de qualquer lugar, em vários dispositivos simultaneamente.',
         'is_addon': False},
        {'feature_key': 'financial_payables', 'name': 'Financeiro: Contas a Pagar',
         'description': 'Controle suas despesas e contas a pagar diretamente pelo sistema.', 'is_addon': False},
    ]

    # Cria/atualiza features
    for feature_data in features_data:
        feature = db.query(models.Feature).filter_by(feature_key=feature_data['feature_key']).first()
        if not feature:
            feature = models.Feature(**feature_data)
            db.add(feature)
        else:
            for key, value in feature_data.items():
                setattr(feature, key, value)

    db.flush()

    # Nosso plano diferenciado
    plans_data = [
        {
            'plan_name': 'Plano Parceiro',
            'available': True,
            # NOSSO VALOR JUSTO
            'minimum_fee': 2990,  # R$ 29,90
            'revenue_percentage': Decimal('0.029'),  # 2.9%
            'revenue_cap_fee': 19900,  # R$ 199,00
            'percentage_tier_start': 110000,  # R$ 1.100,00
            'percentage_tier_end': 700000,  # R$ 7.000,00
            # NOSSOS DIFERENCIAIS
            'first_month_free': True,
            'second_month_discount': Decimal('0.50'),
            'third_month_discount': Decimal('0.75'),
            'support_type': 'Suporte Parceiro Dedicado',
        }
    ]

    for plan_data in plans_data:
        plan = db.query(models.Plans).filter_by(plan_name=plan_data['plan_name']).first()
        if not plan:
            plan = models.Plans(**plan_data)
            db.add(plan)
        else:
            for key, value in plan_data.items():
                setattr(plan, key, value)

    db.commit()
    print("✅ Estrutura de valor único definida com sucesso!")


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
         # ✅ TEMPLATE ATUALIZADO PARA O MODELO DE MENU
         'default_content': '{greeting}, {client.name}! 👋 Eu sou o assistente virtual da {company.name}. Como posso te ajudar hoje?\n\n'
                            'Digite o NÚMERO da opção desejada:\n'
                            '*1️⃣ - Ver Cardápio e Promoções*\n'
                            '*2️⃣ - Horário de Funcionamento*\n'
                            '*3️⃣ - Nosso Endereço*\n'
                            '*4️⃣ - Falar com um Atendente*',
         'available_variables': ['greeting', 'client.name', 'company.name']},


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
         'available_variables': ['info.url', 'company.address']},
        {'message_key': 'business_hours_message', 'name': 'Mensagem de horário de funcionamento',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': '⏰ <b>Aqui está nosso horário de atendimento:</b> \n\n{company.business_hours} \n\nEstamos disponíveis durante esses horários para oferecer o melhor em serviço e delícias culinárias. \n\n🔗 <b>Faça seu pedido aqui:</b>{company.url_products}',
         'available_variables': ['company.business_hours', 'company.url_products']},


        {'message_key': 'farewell_message', 'name': 'Mensagem de Despedida/Agradecimento',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'De nada, {client.name}! 😊\nSe precisar de mais alguma coisa, é só chamar!',
         'available_variables': ['client.name']},

        # ✅ NOVOS TEMPLATES PARA ATENDIMENTO HUMANO
        {'message_key': 'human_support_message', 'name': 'Mensagem de Transferência para Atendente',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'Ok, estou transferindo seu atendimento. Por favor, aguarde, um de nossos atendentes irá te responder em breve por aqui mesmo.  atendimento.',
         'available_variables': []},

        {'message_key': 'human_support_active', 'name': 'Lembrete de Atendimento Ativo',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         'default_content': 'Você já está em atendimento com um de nossos atendentes. Por favor, aguarde o retorno dele(a).',
         'available_variables': []},


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

        # ✅ NOVO TEMPLATE PARA O RESUMO DO PEDIDO
        {'message_key': 'new_order_summary', 'name': 'Resumo do Novo Pedido',
         'message_group': ChatbotMessageGroupEnum.ORDER_UPDATES,
         'description': 'Mensagem detalhada enviada ao cliente assim que um novo pedido é criado.',
         'default_content': 'Este é um template estruturado. O conteúdo é gerado automaticamente pelo sistema.',
         'available_variables': ['order.public_id', 'client.name', 'client.phone', 'order.items', 'order.subtotal',
                                 'order.delivery_fee', 'order.total', 'payment.method', 'delivery.address',
                                 'order.tracking_link']},


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
         'available_variables': ['order.public_id']},

        {'message_key': 'order_not_found', 'name': 'Pedido Não Encontrado',
         'message_group': ChatbotMessageGroupEnum.CUSTOMER_QUESTIONS,
         # ✅ CONTEÚDO ATUALIZADO
         'default_content': 'Olá, {client.name}. Não encontrei nenhum pedido feito hoje com o seu número de WhatsApp. Se você pediu usando outro número, por favor, me informe qual é.',
         'available_variables': ['client.name']},

        # ✅ NOVO TEMPLATE DE REATIVAÇÃO
        {
            'message_key': 'customer_reactivation',
            'name': 'Reativação de Cliente Inativo',
            'message_group': ChatbotMessageGroupEnum.LOYALTY,  # Ou SALES_RECOVERY
            'default_content': 'Olá, {client.name}! 👋 Sentimos sua falta aqui no(a) {store.name}.\n\nPara celebrar seu retorno, preparamos um cupom especial para você: *{coupon_code}*.\n\nVolte e aproveite! Peça agora em: {store.url}',
            'available_variables': ['client.name', 'store.name', 'coupon_code', 'store.url']
        }
    ]

    for t_data in templates:
        exists = db.query(models.ChatbotMessageTemplate).filter_by(message_key=t_data['message_key']).first()
        if not exists:
            template = models.ChatbotMessageTemplate(**t_data)
            db.add(template)

    db.commit()


