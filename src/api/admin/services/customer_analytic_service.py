# Crie este novo arquivo: src/api/admin/logic/customer_analytic_logic.py

from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from src.api.admin.schemas.analytic_customer_schema import CustomerAnalyticsResponse, KeyCustomerMetrics, RfmSegment, \
    CustomerMetric


# --- FUNÇÃO PRINCIPAL (A que você vai chamar) ---

async def get_customer_analytics_for_store(db: AsyncSession, store_id: int,
                                           period_in_days: int = 30) -> CustomerAnalyticsResponse:
    """
    Orquestra a busca e o processamento de todos os dados de análise de clientes.
    """
    start_date = datetime.now() - timedelta(days=period_in_days)
    today = datetime.now()

    # 1. CONSULTA ÚNICA PARA AGREGAR DADOS DE CLIENTES
    # Esta query busca todos os clientes e resume seu histórico de compras.
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
    result = await db.execute(text(query), {"store_id": store_id})
    customer_data = [dict(row) for row in result.mappings()]

    if not customer_data:
        # Retorna um objeto vazio se não houver dados de clientes
        return CustomerAnalyticsResponse(
            key_metrics=KeyCustomerMetrics(new_customers=0, returning_customers=0, retention_rate=0.0),
            segments=[]
        )

    # 2. CÁLCULO DAS MÉTRICAS CHAVE
    new_customers_count = sum(1 for c in customer_data if c['first_order_date'] >= start_date.date())
    total_customers_in_period = sum(1 for c in customer_data if c['last_order_date'] >= start_date.date())
    returning_customers_count = total_customers_in_period - new_customers_count

    # Cálculo simples de retenção para V1
    retention_rate = (
                returning_customers_count / total_customers_in_period * 100) if total_customers_in_period > 0 else 0.0

    key_metrics = KeyCustomerMetrics(
        new_customers=new_customers_count,
        returning_customers=returning_customers_count,
        retention_rate=round(retention_rate, 2)
    )

    # 3. SEGMENTAÇÃO RFM (Recência, Frequência, Valor Monetário)
    segments = _perform_rfm_segmentation(customer_data, today)

    # 4. MONTAGEM DA RESPOSTA FINAL
    return CustomerAnalyticsResponse(
        key_metrics=key_metrics,
        segments=segments,
    )


# --- FUNÇÃO AUXILIAR PARA A LÓGICA RFM ---

def _perform_rfm_segmentation(customer_data: List[Dict], today: datetime) -> List[RfmSegment]:
    """Usa a biblioteca Pandas para calcular e segmentar clientes com base em RFM."""
    df = pd.DataFrame(customer_data)
    df['recency'] = (today.date() - pd.to_datetime(df['last_order_date']).dt.date).dt.days

    # Criando scores de 1 a 4 (4 é o melhor)
    df['R_score'] = pd.qcut(df['recency'], 4, labels=[4, 3, 2, 1])  # Menor recency (dias) = maior score
    df['F_score'] = pd.qcut(df['order_count'].rank(method='first'), 4,
                            labels=[1, 2, 3, 4])  # Maior frequência = maior score
    df['M_score'] = pd.qcut(df['total_spent'].rank(method='first'), 4, labels=[1, 2, 3, 4])  # Maior valor = maior score

    df['RFM_score'] = df['R_score'].astype(str) + df['F_score'].astype(str) + df['M_score'].astype(str)

    # Mapeamento de segmentos
    segment_map = {
        r'[3-4][3-4][3-4]': '🏆 Campeões',
        r'[3-4][1-2][1-4]': '🙂 Clientes Fiéis',
        r'[1-2][3-4][3-4]': '⚠️ Em Risco',
        r'[1-2][1-2][1-4]': '💤 Hibernando',
        r'[3-4][3-4][1-2]': '💰 Grandes Gastadores',
        r'4[1-4][1-4]': '⭐ Clientes Novos'
    }

    df['segment'] = df['RFM_score'].replace(segment_map, regex=True)
    # Garante que qualquer combinação não mapeada receba um nome padrão
    df['segment'] = df.apply(lambda row: row['segment'] if row['segment'] in segment_map.values() else 'Outros', axis=1)

    # Dicionário com descrições e sugestões para cada segmento
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

    # Agrupando os clientes por segmento para a resposta final
    final_segments = []
    for segment_name, group in df.groupby('segment'):
        desc, sugg = segment_details.get(segment_name, ("", ""))
        final_segments.append(RfmSegment(
            segment_name=segment_name,
            description=desc,
            suggestion=sugg,
            customers=[CustomerMetric(**row) for row in group.to_dict('records')]
        ))

    return sorted(final_segments, key=lambda s: s.segment_name)  # Ordena para consistência