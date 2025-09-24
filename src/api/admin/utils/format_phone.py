# Adicione esta função no seu arquivo de rotas do chatbot
import re

def format_phone_number(phone_number: str) -> str:
    """Limpa e formata o número de telefone para o padrão DDI+DDD+NÚMERO."""
    if not phone_number:
        raise ValueError("Número de telefone não pode ser vazio.")

    # 1. Remove todos os caracteres não numéricos
    cleaned_number = re.sub(r'\D', '', phone_number)

    # 2. Verifica o tamanho e adiciona o código do país (55) se necessário
    # Número com DDD (ex: 27999998888) -> 11 dígitos
    # Número com DDI (ex: 5527999998888) -> 13 dígitos
    if len(cleaned_number) == 11:
        # Assumimos que é um número brasileiro sem DDI, então adicionamos
        return f"55{cleaned_number}"
    elif len(cleaned_number) == 13 and cleaned_number.startswith("55"):
        # O número já está no formato correto
        return cleaned_number
    else:
        # Se não se encaixar nos padrões, é inválido
        raise ValueError(f"Formato de número de telefone inválido: {phone_number}")