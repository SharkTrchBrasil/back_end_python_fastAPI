# Em src/api/admin/logic/customer_analytic_logic.py

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session  # ✅ Usamos a Session síncrona
import pandas as pd

# Importe seus schemas
from src.api.admin.schemas.analytic_customer_schema import (
    CustomerAnalyticsResponse, KeyCustomerMetrics, RfmSegment, CustomerMetric
)


# --- FUNÇÃO SÍNCRONA AUXILIAR (SÓ PARA O BANCO) ---

def _fetch_customer_data_from_db(db: Session, store_id: int) -> List[Dict]:
    """
    Esta função contém APENAS a lógica de banco de dados.
    Ela é síncrona.
    """
    query = f"""
    SELECT
        u.id AS customer_id,
        u.name,
        COUNT(o.id) AS order_count,
        SUM(o.total) AS total_spent,
        MAX(DATE(o.created_at)) AS last_order_date,
        MIN(DATE(o.created_at)) AS first_order_date
    FROM
        users u
    JOIN
        orders o ON u.id = o.user_id
    WHERE
        o.store_id = :store_id
    GROUP BY
        u.id, u.name;
    """
    # Usamos parâmetros nomeados para segurança
    result = db.execute(text(query), {"store_id": store_id})
    return [dict(row) for row in result.mappings()]


# --- FUNÇÃO PRINCIPAL ASSÍNCRONA (A que você chama) ---

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


# --- FUNÇÃO AUXILIAR RFM (sem alterações) ---

def _perform_rfm_segmentation(customer_data: List[Dict], today: datetime) -> List[RfmSegment]:
    # ... (seu código de RFM aqui, ele já está correto) ...
    df = pd.DataFrame(customer_data)
    df['recency'] = (today.date() - pd.to_datetime(df['last_order_date']).dt.date).dt.days
    df['R_score'] = pd.qcut(df['recency'], 4, labels=[4, 3, 2, 1], duplicates='drop')
    df['F_score'] = pd.qcut(df['order_count'].rank(method='first'), 4, labels=[1, 2, 3, 4], duplicates='drop')
    df['M_score'] = pd.qcut(df['total_spent'].rank(method='first'), 4, labels=[1, 2, 3, 4], duplicates='drop')
    df['RFM_score'] = df['R_score'].astype(str) + df['F_score'].astype(str) + df['M_score'].astype(str)
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
        # ✅ Garante que o nome do segmento seja sempre uma string
        str_segment_name = str(segment_name)

        desc, sugg = segment_details.get(str_segment_name, ("", ""))
        final_segments.append(RfmSegment(
            segment_name=str_segment_name,  # <-- Agora está corrigido
            description=desc,
            suggestion=sugg,
            customers=[CustomerMetric(**row) for row in group.to_dict('records')]
        ))
    return sorted(final_segments, key=lambda s: s.segment_name)