# from jinja2 import Environment, FileSystemLoader
# from weasyprint import HTML
# from src.api.schemas.performance import StorePerformanceSchema
#
#
# def create_performance_pdf(
#         store_name: str,
#         start_date: str,
#         end_date: str,
#         performance_data: StorePerformanceSchema
# ) -> bytes:
#     """
#     Gera um PDF a partir de um template HTML e dados de performance.
#     """
#     # Configura o Jinja2 para ler o template da pasta 'templates'
#     env = Environment(loader=FileSystemLoader("src/templates"))
#     template = env.get_template("report.html")
#
#     # Renderiza o template com os dados
#     html_out = template.render(
#         store_name=store_name,
#         start_date=start_date,
#         end_date=end_date,
#         data=performance_data
#     )
#
#     # Converte o HTML renderizado para PDF em memória
#     pdf_bytes = HTML(string=html_out).write_pdf()
#
#     return pdf_bytes