# < !DOCTYPE
# html >
# < html
# lang = "pt-BR" >
# < head >
# < meta
# charset = "UTF-8" >
# < title > Relatório
# de
# Desempenho < / title >
# < style >
# body
# {font - family: 'Helvetica', sans - serif;
# font - size: 10
# px;
# color:  # 333; }
# h1
# {color:  # d32f2f; font-size: 24px; text-align: center; }
#      h2 {font - size: 16px;
# border - bottom: 1
# px
# solid  # eee; padding-bottom: 5px; margin-top: 20px;}
# table
# {width: 100 %;
# border - collapse: collapse;
# margin - top: 10
# px;}
# th, td
# {border: 1px solid  # ddd; padding: 6px; text-align: left; }
#  th {background - color:  # f2f2f2; }
#     .summary - card {
#      border: 1px solid  # ddd; border-radius: 5px; padding: 10px;
#      display: inline - block;
# width: 30 %;
# margin: 5
# px;
# text - align: center;
# }
# .summary - card.title
# {font - size: 11px;
# color:  # 666; }
# .summary - card.value
# {font - size: 16px;
# font - weight: bold;}
# < / style >
#     < / head >
#         < body >
#         < h1 > Relatório
# de
# Desempenho < / h1 >
#                < p
# style = "text-align: center;" > < strong > Loja: < / strong > {{store_name}} < / p >
#                                                                                  < p
# style = "text-align: center;" > < strong > Período: < / strong > {{start_date}}
# a
# {{end_date}} < / p >
#
#                  < h2 > Resumo
# de
# Vendas < / h2 >
#            < div
#
#
# class ="summary-card" >
#
# < div
#
#
# class ="title" > Faturamento < / div >
#
# < div
#
#
# class ="value" > R$ {{"%.2f" | format(data.summary.total_value.current)}} < / div >
#
# < / div >
# < div
#
#
# class ="summary-card" >
#
# < div
#
#
# class ="title" > Lucro Bruto < / div >
#
# < div
#
#
# class ="value" > R$ {{"%.2f" | format(data.gross_profit.current)}} < / div >
#
# < / div >
# < div
#
#
# class ="summary-card" >
#
# < div
#
#
# class ="title" > Vendas Concluídas < / div >
#
# < div
#
#
# class ="value" > {{data.summary.completed_sales.current | int}} < / div >
#
# < / div >
#
# < h2 > Top
# 5
# Produtos
# Mais
# Vendidos < / h2 >
# < table >
# < thead >
# < tr > < th > Produto < / th > < th > Qtd.Vendida < / th > < th > Valor
# Total < / th > < / tr >
# < / thead >
# < tbody >
# { %
# for product in data.top_selling_products %}
# < tr >
# < td > {{product.product_name}} < / td >
# < td > {{product.quantity_sold}} < / td >
# < td > R$ {{"%.2f" | format(product.total_value)}} < / td >
# < / tr >
# { % endfor %}
# < / tbody >
# < / table >
#
# < / body >
# < / html >