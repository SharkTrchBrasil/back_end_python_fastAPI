#!/usr/bin/env python3
"""
Script para gerar chave de criptografia
Execute: python generate_encryption_key.py
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print("\n✅ Chave de criptografia gerada com sucesso!")
    print("\n📋 Adicione esta linha no seu .env:")
    print(f"\nENCRYPTION_KEY={key.decode()}")
    print("\n🚨 NUNCA commite esta chave no Git!\n")