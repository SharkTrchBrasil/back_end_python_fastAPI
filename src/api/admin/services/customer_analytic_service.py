# Em src/api/admin/logic/customer_analytic_logic.py

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session  # ✅ Usamos a Session síncrona
import pandas as pd

# Importe seus schemas
from src.api.schemas.analytic_customer_schema import (
    CustomerAnalyticsResponse, KeyCustomerMetrics, RfmSegment, CustomerMetric
)



def _fetch_customer_data_from_db(db: Session, store_id: int) -> List[Dict]:
    """
    Esta função contém APENAS a lógica de banco de dados.
    Ela é síncrona.
    """
    # ✅ QUERY CORRIGIDA PARA USAR A TABELA 'customers'
    query = f"""
    SELECT
        c.id AS customer_id,   -- MUDOU AQUI (de u.id para c.id)
        c.name,                -- MUDOU AQUI (de u.name para c.name)
        COUNT(o.id) AS order_count,
        SUM(o.discounted_total_price) AS total_spent,
        MAX(DATE(o.created_at)) AS last_order_date,
        MIN(DATE(o.created_at)) AS first_order_date
    FROM
        customers c            -- MUDOU AQUI (de users u para customers c)
    JOIN
        orders o ON c.id = o.customer_id  -- MUDOU AQUI (de u.id para c.id)
    WHERE
        o.store_id = :store_id
        AND o.order_status = 'delivered' -- Boa prática: Analisar apenas pedidos concluídos
    GROUP BY
        c.id, c.name;          -- MUDOU AQUI (de u.id, u.name para c.id, c.name)
    """
    # Usamos parâmetros nomeados para segurança
    result = db.execute(text(query), {"store_id": store_id})
    return [dict(row) for row in result.mappings()]



async def get_customer_analytics_for_store(db: Session, store_id: int,
                                           period_in_days: int = 30) -> CustomerAnalyticsResponse:
    """
    Orquestra a busca e o processamento dos dados.
    """
    # 1. EXECUTA A QUERY SÍNCRONA EM UMA THREAD SEPARADA
    customer_data = await asyncio.to_thread(_fetch_customer_data_from_db, db, store_id)

    # Se não houver dados, retorna um objeto vazio.
    if not customer_data:
        return CustomerAnalyticsResponse(
            key_metrics=KeyCustomerMetrics(new_customers=0, returning_customers=0, retention_rate=0.0),
            segments=[]
        )

    # 2. PROCESSAMENTO E CÁLCULOS (feitos no Python, fora da função de query)
    today = datetime.now()
    start_date = today - timedelta(days=period_in_days)

    new_customers_count = sum(1 for c in customer_data if c['first_order_date'] >= start_date.date())
    total_customers_in_period = sum(1 for c in customer_data if c['last_order_date'] >= start_date.date())
    returning_customers_count = total_customers_in_period - new_customers_count
    retention_rate = (
                returning_customers_count / total_customers_in_period * 100) if total_customers_in_period > 0 else 0.0

    key_metrics = KeyCustomerMetrics(
        new_customers=new_customers_count,
        returning_customers=returning_customers_count,
        retention_rate=round(retention_rate, 2)
    )

    segments = _perform_rfm_segmentation(customer_data, today)

    # 3. MONTAGEM DA RESPOSTA FINAL
    return CustomerAnalyticsResponse(
        key_metrics=key_metrics,
        segments=segments,
    )


# Em src/api/admin/logic/customer_analytic_logic.py

def _perform_rfm_segmentation(customer_data: List[Dict], today: datetime) -> List[RfmSegment]:
    if not customer_data:
        return []

    df = pd.DataFrame(customer_data)

    # --- CORREÇÃO APLICADA AQUI ---
    # Converte a coluna para datetime, tratando erros
    df['last_order_date'] = pd.to_datetime(df['last_order_date'], errors='coerce')
    df['recency'] = (today - df['last_order_date']).dt.days
    df['recency'].fillna(9999, inplace=True)  # Garante que clientes sem data não quebrem o código

    # Lógica de pontuação robusta que não quebra com dados repetidos
    try:
        # Para Recência (menor é melhor), o score é invertido.
        r_labels = pd.qcut(df['recency'], 4, labels=False, duplicates='drop')
        df['R_score'] = 4 - r_labels.astype(int)

        # Para Frequência e Gasto (maior é melhor), o score é direto.
        f_labels = pd.qcut(df['order_count'].rank(method='first'), 4, labels=False, duplicates='drop')
        df['F_score'] = f_labels.astype(int) + 1

        m_labels = pd.qcut(df['total_spent'].rank(method='first'), 4, labels=False, duplicates='drop')
        df['M_score'] = m_labels.astype(int) + 1

    except ValueError:
        # Fallback para casos com pouquíssimos dados (ex: 1 cliente)
        # Atribui um score médio para todos
        df['R_score'] = 2
        df['F_score'] = 2
        df['M_score'] = 2

    df['RFM_score'] = df['R_score'].astype(str) + df['F_score'].astype(str) + df['M_score'].astype(str)

    # --- O RESTO DO CÓDIGO CONTINUA IGUAL ---
    segment_map = {
        r'[3-4][3-4][3-4]': '🏆 Campeões', r'[3-4][1-2][1-4]': '🙂 Clientes Fiéis',
        r'[1-2][3-4][3-4]': '⚠️ Em Risco', r'[1-2][1-2][1-4]': '💤 Hibernando',
        r'[3-4][3-4][1-2]': '💰 Grandes Gastadores', r'4[1-4][1-4]': '⭐ Clientes Novos'
    }
    df['segment'] = df['RFM_score'].replace(segment_map, regex=True)
    df['segment'] = df.apply(lambda row: row['segment'] if row['segment'] in segment_map.values() else 'Outros', axis=1)
    segment_details = {
        '🏆 Campeões': ("Compram com frequência, recentemente e gastam muito.",
                       "Crie um programa VIP ou ofereça um brinde exclusivo."),
        '🙂 Clientes Fiéis': ("Compram com boa frequência, mas gastam menos.",
                             "Ofereça produtos de maior valor (upsell) e programas de pontos."),
        '⚠️ Em Risco': ("Costumavam comprar bem, mas não aparecem há um tempo.",
                        "Envie uma campanha de reativação com um cupom de 'sentimos sua falta'."),
        '💤 Hibernando': ("Não compram há muito tempo e podem ser perdidos.",
                         "Ofereça um desconto agressivo para uma última tentativa de reativação."),
        '💰 Grandes Gastadores': ("Fizeram compras de alto valor, mas com baixa frequência.",
                                 "Ofereça produtos exclusivos e acesso antecipado a novidades."),
        '⭐ Clientes Novos': ("Fizeram a primeira compra recentemente.",
                             "Garanta uma ótima primeira experiência e envie um cupom para a segunda compra."),
        'Outros': ("Clientes com comportamento variado.", "Monitore para identificar padrões emergentes.")
    }
    final_segments = []
    for segment_name, group in df.groupby('segment'):
        str_segment_name = str(segment_name)
        desc, sugg = segment_details.get(str_segment_name, ("", ""))
        final_segments.append(RfmSegment(
            segment_name=str_segment_name,
            description=desc,
            suggestion=sugg,
            customers=[CustomerMetric(**row) for row in group.to_dict('records')]
        ))
    return sorted(final_segments, key=lambda s: s.segment_name)