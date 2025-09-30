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
def seed_segments(db: Session):
    """
    Cria os segmentos/specialidades padrão para as lojas
    """
    print("Iniciando a semeadura de segmentos...")

    segments_data = [
        # Segmentos de Comida
        {'name': 'Pizzaria', 'description': 'Lojas especializadas em pizzas'},
        {'name': 'Hamburgueria', 'description': 'Lojas especializadas em hambúrgueres'},
        {'name': 'Restaurante', 'description': 'Restaurantes com cardápio variado'},
        {'name': 'Lanchonete', 'description': 'Lanches rápidos e refeições leves'},
        {'name': 'Pastelaria', 'description': 'Especializada em pastéis e salgados'},
        {'name': 'Churrascaria', 'description': 'Carnes assadas e churrasco'},
        {'name': 'Comida Japonesa', 'description': 'Sushi, temaki e culinária japonesa'},
        {'name': 'Comida Chinesa', 'description': 'Culinária chinesa e oriental'},
        {'name': 'Comida Mexicana', 'description': 'Tacos, burritos e culinária mexicana'},
        {'name': 'Comida Italiana', 'description': 'Massas, risotos e culinária italiana'},
        {'name': 'Comida Árabe', 'description': 'Esfihas, quibes e culinária árabe'},
        {'name': 'Açaí e Sorveteria', 'description': 'Açaí, sorvetes e sobremesas geladas'},
        {'name': 'Padaria', 'description': 'Pães, bolos e confeitaria'},
        {'name': 'Confeitaria', 'description': 'Bolos, doces e sobremesas'},
        {'name': 'Cafeteria', 'description': 'Cafés especiais e acompanhamentos'},
        {'name': 'Food Truck', 'description': 'Comida de rua e food truck'},
        {'name': 'Marmitaria', 'description': 'Marmitas e comida caseira'},
        {'name': 'Salgaderia', 'description': 'Salgados assados e fritos'},
        {'name': 'Creperia', 'description': 'Crepes doces e salgados'},
        {'name': 'Culinária Vegana', 'description': 'Comida 100% vegetal e vegana'},
        {'name': 'Culinária Vegetariana', 'description': 'Comida sem carne'},
        {'name': 'Frutos do Mar', 'description': 'Pratos com peixes e frutos do mar'},
        {'name': 'Culinária Baiana', 'description': 'Comida típica da Bahia'},
        {'name': 'Culinária Mineira', 'description': 'Comida típica de Minas Gerais'},

        # Segmentos de Bebidas
        {'name': 'Bebidas', 'description': 'Lojas especializadas em bebidas'},
        {'name': 'Sucos Naturais', 'description': 'Sucos, vitaminas e bebidas naturais'},
        {'name': 'Drinks e Coquetéis', 'description': 'Bebidas alcoólicas e coquetéis'},

        # Outros Segmentos
        {'name': 'Mercado', 'description': 'Mercados e mercearias'},
        {'name': 'Farmácia', 'description': 'Produtos farmacêuticos e saúde'},
        {'name': 'Conveniência', 'description': 'Lojas de conveniência'},
        {'name': 'Floricultura', 'description': 'Flores e arranjos'},
        {'name': 'Pet Shop', 'description': 'Produtos para animais de estimação'},
        {'name': 'Presentes', 'description': 'Lojas de presentes e variedades'},
        {'name': 'Vestuário', 'description': 'Roupas e acessórios'},
        {'name': 'Eletrônicos', 'description': 'Aparelhos eletrônicos e tecnologia'},
        {'name': 'Casa e Decoração', 'description': 'Artigos para casa e decoração'},
        {'name': 'Livraria', 'description': 'Livros e material de papelaria'},
        {'name': 'Esportes', 'description': 'Artigos esportivos'},
        {'name': 'Beleza e Cosméticos', 'description': 'Produtos de beleza e cuidados pessoais'},
        {'name': 'Papelaria', 'description': 'Material escolar e de escritório'},
    ]

    for segment_data in segments_data:
        segment = db.query(models.Segment).filter_by(name=segment_data['name']).first()
        if not segment:
            segment = models.Segment(**segment_data)
            db.add(segment)
            print(f"Segmento '{segment_data['name']}' criado.")
        else:
            # Atualiza descrição se necessário
            if segment.description != segment_data['description']:
                segment.description = segment_data['description']
                print(f"Segmento '{segment_data['name']}' atualizado.")

    db.commit()
    print("✅ Segmentos criados/atualizados com sucesso!")

def seed_payment_methods(db: Session):
    """
    Cria os grupos, categorias e métodos de pagamento padrão
    """
    print("Iniciando a semeadura de métodos de pagamento...")

    # Grupos de pagamento
    groups_data = [
        {
            'name': 'online_payments',
            'title': 'Pagamento pelo App',
            'description': 'Pagamentos realizados diretamente pelo aplicativo',
            'priority': 1
        },
        {
            'name': 'delivery_payments',
            'title': 'Pagamento na Entrega',
            'description': 'Pagamentos realizados no momento da entrega/retirada',
            'priority': 2
        }
    ]

    # Criar/atualizar grupos
    for group_data in groups_data:
        group = db.query(models.PaymentMethodGroup).filter_by(name=group_data['name']).first()
        if not group:
            group = models.PaymentMethodGroup(**group_data)
            db.add(group)
            print(f"Grupo de pagamento '{group_data['name']}' criado.")
        else:
            for key, value in group_data.items():
                setattr(group, key, value)

    db.flush()

    # Categorias de pagamento
    categories_data = [
        # Pagamento Online
        {
            'name': 'pix_online',
            'priority': 1,
            'group_name': 'online_payments'
        },
        {
            'name': 'credit_card_online',
            'priority': 2,
            'group_name': 'online_payments'
        },
        {
            'name': 'debit_card_online',
            'priority': 3,
            'group_name': 'online_payments'
        },

        # Pagamento na Entrega
        {
            'name': 'cash_delivery',
            'priority': 1,
            'group_name': 'delivery_payments'
        },
        {
            'name': 'pix_delivery',
            'priority': 2,
            'group_name': 'delivery_payments'
        },
        {
            'name': 'credit_card_delivery',
            'priority': 3,
            'group_name': 'delivery_payments'
        },
        {
            'name': 'debit_card_delivery',
            'priority': 4,
            'group_name': 'delivery_payments'
        }
    ]

    # Criar/atualizar categorias
    for category_data in categories_data:
        group = db.query(models.PaymentMethodGroup).filter_by(name=category_data.pop('group_name')).first()
        category = db.query(models.PaymentMethodCategory).filter_by(name=category_data['name']).first()

        if not category:
            category_data['group_id'] = group.id
            category = models.PaymentMethodCategory(**category_data)
            db.add(category)
            print(f"Categoria de pagamento '{category_data['name']}' criada.")
        else:
            category.group_id = group.id
            for key, value in category_data.items():
                if key != 'group_name':
                    setattr(category, key, value)

    db.flush()

    # Métodos de pagamento específicos
    payment_methods_data = [
        # PIX Online
        {
            'name': 'pix',
            'description': 'Pagamento instantâneo via PIX',
            'method_type': 'pix',
            'icon_key': 'pix',
            'is_globally_enabled': True,
            'requires_details': False,
            'category_name': 'pix_online'
        },

        # Cartão de Crédito Online
        {
            'name': 'credit_card_visa',
            'description': 'Cartão de crédito Visa',
            'method_type': 'credit_card',
            'icon_key': 'visa',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },
        {
            'name': 'credit_card_mastercard',
            'description': 'Cartão de crédito Mastercard',
            'method_type': 'credit_card',
            'icon_key': 'mastercard',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },
        {
            'name': 'credit_card_amex',
            'description': 'Cartão de crédito American Express',
            'method_type': 'credit_card',
            'icon_key': 'amex',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },
        {
            'name': 'credit_card_elo',
            'description': 'Cartão de crédito Elo',
            'method_type': 'credit_card',
            'icon_key': 'elo',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },
        {
            'name': 'credit_card_hipercard',
            'description': 'Cartão de crédito Hipercard',
            'method_type': 'credit_card',
            'icon_key': 'hipercard',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },
        {
            'name': 'credit_card_diners',
            'description': 'Cartão de crédito Diners Club',
            'method_type': 'credit_card',
            'icon_key': 'diners',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_online'
        },

        # Cartão de Débito Online
        {
            'name': 'debit_card_visa',
            'description': 'Cartão de débito Visa',
            'method_type': 'debit_card',
            'icon_key': 'visa',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'debit_card_online'
        },
        {
            'name': 'debit_card_mastercard',
            'description': 'Cartão de débito Mastercard',
            'method_type': 'debit_card',
            'icon_key': 'mastercard',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'debit_card_online'
        },
        {
            'name': 'debit_card_elo',
            'description': 'Cartão de débito Elo',
            'method_type': 'debit_card',
            'icon_key': 'elo',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'debit_card_online'
        },

        # Dinheiro na Entrega
        {
            'name': 'cash',
            'description': 'Pagamento em dinheiro',
            'method_type': 'cash',
            'icon_key': 'cash',
            'is_globally_enabled': True,
            'requires_details': False,
            'category_name': 'cash_delivery'
        },

        # PIX na Entrega
        {
            'name': 'pix_delivery',
            'description': 'PIX na hora da entrega',
            'method_type': 'pix',
            'icon_key': 'pix',
            'is_globally_enabled': True,
            'requires_details': False,
            'category_name': 'pix_delivery'
        },

        # Cartão de Crédito na Entrega
        {
            'name': 'credit_card_machine',
            'description': 'Cartão na máquina na entrega',
            'method_type': 'credit_card',
            'icon_key': 'credit_card',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'credit_card_delivery'
        },

        # Cartão de Débito na Entrega
        {
            'name': 'debit_card_machine',
            'description': 'Débito na máquina na entrega',
            'method_type': 'debit_card',
            'icon_key': 'debit_card',
            'is_globally_enabled': True,
            'requires_details': True,
            'category_name': 'debit_card_delivery'
        }
    ]

    # Criar/atualizar métodos de pagamento
    for method_data in payment_methods_data:
        category = db.query(models.PaymentMethodCategory).filter_by(name=method_data.pop('category_name')).first()
        method = db.query(models.PlatformPaymentMethod).filter_by(name=method_data['name']).first()

        if not method:
            method_data['category_id'] = category.id
            method = models.PlatformPaymentMethod(**method_data)
            db.add(method)
            print(f"Método de pagamento '{method_data['name']}' criado.")
        else:
            method.category_id = category.id
            for key, value in method_data.items():
                if key != 'category_name':
                    setattr(method, key, value)

    db.commit()
    print("✅ Estrutura de pagamentos criada/atualizada com sucesso!")
