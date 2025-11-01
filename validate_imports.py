#!/usr/bin/env python3
"""
Script para validar importações do Backend
===========================================
Verifica se todos os módulos importados existem e são válidos
"""

import sys
from pathlib import Path

# Adiciona o diretório src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path.parent))

def test_import(module_path: str) -> tuple[bool, str]:
    """Testa uma importação específica"""
    try:
        __import__(module_path)
        return True, "OK"
    except ModuleNotFoundError as e:
        return False, f"ModuleNotFoundError: {str(e)}"
    except ImportError as e:
        return False, f"ImportError: {str(e)}"
    except SyntaxError as e:
        return False, f"SyntaxError: {str(e)}"
    except Exception as e:
        return False, f"Erro: {str(e)}"

def validate_all_imports():
    """Valida todas as importações do __init__.py do admin"""
    admin_init = src_path / 'api' / 'admin' / '__init__.py'
    
    print("🔍 Validando importações do Backend...\n")
    
    issues = []
    successful = []
    
    with open(admin_init, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Detecta importações
            if line.startswith('from src.api.admin.routes'):
                # Extrai o módulo
                module_part = line.split('from src.api.admin.routes.')[1].split()[0]
                
                # Tenta importar
                module_path = f"src.api.admin.routes.{module_part}"
                print(f"Linha {i}: Testando {module_part}...", end=' ')
                
                success, error = test_import(module_path)
                
                if success:
                    # Tenta verificar se tem 'router'
                    try:
                        module = sys.modules[module_path]
                        if hasattr(module, 'router'):
                            print("✅ OK")
                            successful.append(module_part)
                        else:
                            print("⚠️ Não tem 'router'")
                            issues.append((i, module_part, "Não exporta 'router'"))
                    except:
                        print("⚠️ Erro ao verificar router")
                        issues.append((i, module_part, "Erro ao acessar módulo"))
                else:
                    print(f"❌ {error}")
                    issues.append((i, module_part, error))
    
    print("\n" + "="*60)
    print("📊 RESUMO")
    print("="*60)
    print(f"\n✅ Sucesso: {len(successful)}/{len(successful) + len(issues)}")
    print(f"❌ Problemas: {len(issues)}")
    
    if issues:
        print("\n🔴 PROBLEMAS ENCONTRADOS:")
        for line_num, module, error in issues:
            print(f"   Linha {line_num}: {module}")
            print(f"      └─ {error}")
    
    return len(issues) == 0

if __name__ == '__main__':
    success = validate_all_imports()
    sys.exit(0 if success else 1)

