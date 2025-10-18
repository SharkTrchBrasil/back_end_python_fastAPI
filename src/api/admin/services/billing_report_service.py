# src/api/admin/services/billing_report_service.py

from sqlalchemy.orm import Session
from sqlalchemy import extract, desc, func
from decimal import Decimal
from typing import Dict, List
from datetime import datetime, timezone

from src.core import models


class BillingReportService:

    @staticmethod
    def get_monthly_report(db: Session, year: int, month: int) -> Dict:
        """
        Gera relatório detalhado das cobranças do mês.
        """
        charges = db.query(models.MonthlyCharge).filter(
            extract('year', models.MonthlyCharge.charge_date) == year,
            extract('month', models.MonthlyCharge.charge_date) == month
        ).all()

        total_revenue = sum(c.total_revenue for c in charges)
        total_fees = sum(c.calculated_fee for c in charges)

        status_counts = {}
        for charge in charges:
            status_counts[charge.status] = status_counts.get(charge.status, 0) + 1

        return {
            'period': f"{month:02d}/{year}",
            'total_charges': len(charges),
            'total_revenue': float(total_revenue),
            'total_fees': float(total_fees),
            'average_rate': float((total_fees / total_revenue * 100) if total_revenue > 0 else 0),
            'status_breakdown': status_counts,
            'charges_by_store': [
                {
                    'store_id': charge.store_id,
                    'store_name': charge.store.name if charge.store else 'N/A',
                    'revenue': float(charge.total_revenue),
                    'fee': float(charge.calculated_fee),
                    'rate': float(
                        (charge.calculated_fee / charge.total_revenue * 100) if charge.total_revenue > 0 else 0),
                    'status': charge.status,
                    'period': charge.billing_period_start.strftime('%m/%Y'),
                    'benefit_applied': charge.metadata.get('has_special_benefit', False) if charge.metadata else False
                }
                for charge in charges
            ]
        }

    @staticmethod
    def get_store_history(db: Session, store_id: int, months: int = 6) -> List[Dict]:
        """
        Retorna o histórico de cobranças de uma loja específica.
        """
        charges = db.query(models.MonthlyCharge) \
            .filter(models.MonthlyCharge.store_id == store_id) \
            .order_by(desc(models.MonthlyCharge.charge_date)) \
            .limit(months) \
            .all()

        return [
            {
                'period': charge.billing_period_start.strftime('%m/%Y'),
                'revenue': float(charge.total_revenue),
                'fee': float(charge.calculated_fee),
                'rate': float((charge.calculated_fee / charge.total_revenue * 100) if charge.total_revenue > 0 else 0),
                'status': charge.status,
                'charge_date': charge.charge_date.strftime('%d/%m/%Y'),
                'benefit_type': charge.metadata.get('benefit_type', '') if charge.metadata else ''
            }
            for charge in charges
        ]

    @staticmethod
    def get_yearly_summary(db: Session, year: int) -> Dict:
        """
        Retorna um resumo das cobranças por mês do ano.
        """
        summary = {}

        for month in range(1, 13):
            charges = db.query(models.MonthlyCharge).filter(
                extract('year', models.MonthlyCharge.charge_date) == year,
                extract('month', models.MonthlyCharge.charge_date) == month
            ).all()

            if charges:
                total_revenue = sum(c.total_revenue for c in charges)
                total_fees = sum(c.calculated_fee for c in charges)

                summary[f"{month:02d}/{year}"] = {
                    'total_charges': len(charges),
                    'total_revenue': float(total_revenue),
                    'total_fees': float(total_fees),
                    'average_rate': float((total_fees / total_revenue * 100) if total_revenue > 0 else 0),
                    'paid_charges': len([c for c in charges if c.status == 'paid'])
                }

        return summary

    @staticmethod
    def get_benefits_report(db: Session, months: int = 6) -> Dict:
        """
        Relatório focado nos benefícios entregues aos parceiros.
        """
        # Consulta otimizada com filtro de data
        cutoff_date = datetime.now(timezone.utc) - func.make_interval(months=months)

        result = db.query(
            func.count(models.MonthlyCharge.id).label('total_charges'),
            func.sum(models.MonthlyCharge.metadata['has_special_benefit'].as_boolean()).label('benefits_count'),
            func.avg(models.MonthlyCharge.metadata['benefit_percentage'].as_float()).label('avg_benefit'),
            func.avg(models.MonthlyCharge.calculated_fee).label('avg_fee'),
            func.avg(models.MonthlyCharge.metadata['effective_rate'].as_float()).label('avg_effective_rate')
        ).filter(
            models.MonthlyCharge.charge_date >= cutoff_date
        ).first()

        total_benefits_value = 0
        if result.avg_benefit and result.avg_fee and result.benefits_count:
            total_benefits_value = float(result.avg_benefit * result.avg_fee * result.benefits_count / 100)

        return {
            'benefits_analysis': {
                'analysis_period': f"Últimos {months} meses",
                'total_processed_charges': result.total_charges or 0,
                'charges_with_benefits': result.benefits_count or 0,
                'benefits_coverage': f"{((result.benefits_count or 0) / (result.total_charges or 1) * 100):.1f}%",
                'average_benefit_value': float(result.avg_benefit) if result.avg_benefit else 0,
                'total_benefits_delivered': total_benefits_value,
                'average_effective_rate': float(result.avg_effective_rate) if result.avg_effective_rate else 0
            }
        }

    @staticmethod
    def get_partner_performance(db: Session, store_id: int) -> Dict:
        """
        Relatório de performance individual do parceiro.
        """
        charges = db.query(models.MonthlyCharge) \
            .filter(models.MonthlyCharge.store_id == store_id) \
            .order_by(desc(models.MonthlyCharge.charge_date)) \
            .all()

        if not charges:
            return {'error': 'Nenhuma cobrança encontrada para esta loja'}

        total_revenue = sum(c.total_revenue for c in charges)
        total_fees = sum(c.calculated_fee for c in charges)
        benefits_count = sum(1 for c in charges if c.metadata and c.metadata.get('has_special_benefit'))

        return {
            'partner_id': store_id,
            'partner_name': charges[0].store.name if charges[0].store else 'N/A',
            'analysis_period': f"{charges[-1].charge_date.strftime('%m/%Y')} a {charges[0].charge_date.strftime('%m/%Y')}",
            'total_charges': len(charges),
            'total_revenue': float(total_revenue),
            'total_platform_fees': float(total_fees),
            'average_rate': float((total_fees / total_revenue * 100) if total_revenue > 0 else 0),
            'benefits_received': benefits_count,
            'current_status': charges[0].status,
            'months_partnership': charges[0].metadata.get('months_partnership', 0) if charges[0].metadata else 0
        }