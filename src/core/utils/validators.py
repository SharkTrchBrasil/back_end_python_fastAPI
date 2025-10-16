"""
Validadores de dados brasileiros
=================================
Fornece funções de validação para CPF, CNPJ, telefone e CEP.
"""

import re


def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF brasileiro.

    Args:
        cpf: String contendo apenas dígitos (11 caracteres)

    Returns:
        True se o CPF for válido, False caso contrário

    Examples:
        >>> validate_cpf('12345678909')
        True
        >>> validate_cpf('11111111111')
        False
    """
    if not cpf or len(cpf) != 11 or not cpf.isdigit():
        return False

    # CPFs inválidos conhecidos (todos os dígitos iguais)
    if cpf in [str(d) * 11 for d in range(10)]:
        return False

    # Calcula o primeiro dígito verificador
    sum_of_products = sum(int(cpf[i]) * (10 - i) for i in range(9))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if int(cpf[9]) != expected_digit:
        return False

    # Calcula o segundo dígito verificador
    sum_of_products = sum(int(cpf[i]) * (11 - i) for i in range(10))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if int(cpf[10]) != expected_digit:
        return False

    return True


def validate_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro.

    Args:
        cnpj: String contendo apenas dígitos (14 caracteres)

    Returns:
        True se o CNPJ for válido, False caso contrário

    Examples:
        >>> validate_cnpj('11222333000181')
        True
        >>> validate_cnpj('11111111111111')
        False
    """
    if not cnpj or len(cnpj) != 14 or not cnpj.isdigit():
        return False

    # CNPJs inválidos conhecidos (todos os dígitos iguais)
    if cnpj in [str(d) * 14 for d in range(10)]:
        return False

    def calc_digit(cnpj_partial: str, weights: list[int]) -> int:
        """Calcula um dígito verificador"""
        total = sum(int(digit) * weight for digit, weight in zip(cnpj_partial, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    # Pesos para o primeiro dígito verificador
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    first_digit = calc_digit(cnpj[:12], weights_first)

    if int(cnpj[12]) != first_digit:
        return False

    # Pesos para o segundo dígito verificador
    weights_second = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_digit = calc_digit(cnpj[:13], weights_second)

    if int(cnpj[13]) != second_digit:
        return False

    return True


def validate_phone(phone: str) -> bool:
    """
    Valida telefone brasileiro.

    Args:
        phone: String contendo apenas dígitos

    Returns:
        True se o telefone for válido, False caso contrário

    Examples:
        >>> validate_phone('11987654321')  # Celular com 9
        True
        >>> validate_phone('1133334444')   # Fixo
        True
        >>> validate_phone('123')
        False

    Aceita:
        - 10 dígitos: DDD + 8 dígitos (fixo)
        - 11 dígitos: DDD + 9 dígitos (celular)
        - 13 dígitos: 55 + DDD + 9 dígitos (com código do país)
    """
    if not phone or not phone.isdigit():
        return False

    # Remove código do país se presente (55)
    clean_phone = phone
    if phone.startswith('55') and len(phone) in [12, 13]:
        clean_phone = phone[2:]

    # Valida tamanho (10 ou 11 dígitos)
    if len(clean_phone) not in [10, 11]:
        return False

    # Valida DDD (deve estar entre 11 e 99)
    ddd = int(clean_phone[:2])
    if ddd < 11 or ddd > 99:
        return False

    # Se for celular (11 dígitos), o terceiro dígito deve ser 9
    if len(clean_phone) == 11 and clean_phone[2] != '9':
        return False

    return True


def validate_cep(cep: str) -> bool:
    """
    Valida CEP brasileiro.

    Args:
        cep: String contendo apenas dígitos (8 caracteres)

    Returns:
        True se o CEP for válido, False caso contrário

    Examples:
        >>> validate_cep('01310100')
        True
        >>> validate_cep('123')
        False
    """
    if not cep or len(cep) != 8 or not cep.isdigit():
        return False

    # CEP não pode ser 00000000
    if cep == '00000000':
        return False

    return True


def validate_email(email: str) -> bool:
    """
    Valida formato de email.

    Args:
        email: String contendo o email

    Returns:
        True se o email for válido, False caso contrário

    Examples:
        >>> validate_email('usuario@example.com')
        True
        >>> validate_email('invalid-email')
        False
    """
    if not email:
        return False

    # Regex simples mas eficaz para validação de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))