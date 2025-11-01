#!/usr/bin/env python3
"""
Script de Auditoria do Backend
================================
Identifica e corrige problemas de importação, módulos faltantes, etc.
"""

import os
import sys
import ast
import importlib.util
from pathlib import Path
from typing import List, Dict, Tuple

def check_file_exists(file_path: Path) -> bool:
    """Verifica se um arquivo existe"""
    return file_path.exists()

def check_import_syntax(file_path: Path) -> Tuple[bool, str]:
    """Verifica se o arquivo tem sintaxe Python válida"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, ""
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Erro ao ler arquivo: {str(e)}"

def extract_imports(file_path: Path) -> List[Tuple[str, str]]:
    """Extrai todas as importações de um arquivo"""
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(('import', alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(('from', f"{module}.{alias.name}"))
    except:
        pass
    
    return imports

def find_module_file(module_path: str, base_path: Path) -> Path:
    """Encontra o arquivo de um módulo"""
    # Converte path do módulo para path do sistema
    parts = module_path.split('.')
    file_path = base_path / '/'.join(parts)
    
    # Tenta diferentes extensões
    for ext in ['.py', '']:
        if (file_path.with_suffix('.py')).exists():
            return file_path.with_suffix('.py')
        if (file_path / '__init__.py').exists():
            return file_path / '__init__.py'
    
    return None

def audit_backend():
    """Executa auditoria completa do backend"""
    backend_path = Path(__file__).parent / 'src'
    issues = []
    
    print("🔍 Iniciando auditoria do Backend...\n")
    
    # 1. Verifica arquivo principal
    main_file = backend_path.parent / 'src' / 'main.py'
    if not main_file.exists():
        issues.append(('CRITICAL', 'main.py não encontrado', str(main_file)))
    else:
        print(f"✅ main.py encontrado")
        valid, error = check_import_syntax(main_file)
        if not valid:
            issues.append(('CRITICAL', f'Erro de sintaxe em main.py: {error}', str(main_file)))
    
    # 2. Verifica __init__.py do admin
    admin_init = backend_path / 'api' / 'admin' / '__init__.py'
    if not admin_init.exists():
        issues.append(('CRITICAL', '__init__.py do admin não encontrado', str(admin_init)))
    else:
        print(f"✅ {admin_init.name} encontrado")
        valid, error = check_import_syntax(admin_init)
        if not valid:
            issues.append(('CRITICAL', f'Erro de sintaxe: {error}', str(admin_init)))
        
        # Extrai importações
        imports = extract_imports(admin_init)
        print(f"   └─ {len(imports)} importações encontradas")
        
        # Verifica cada importação
        routes_path = backend_path / 'api' / 'admin' / 'routes'
        for imp_type, imp_name in imports:
            if 'routes.' in imp_name:
                # Extrai nome do módulo
                module_name = imp_name.split('routes.')[-1].split()[0]
                route_file = routes_path / f"{module_name}.py"
                
                if not route_file.exists():
                    issues.append(('ERROR', f'Módulo não encontrado: {module_name}', str(route_file)))
                    print(f"   ❌ {module_name} não encontrado")
                else:
                    valid, error = check_import_syntax(route_file)
                    if not valid:
                        issues.append(('ERROR', f'Erro de sintaxe em {module_name}: {error}', str(route_file)))
    
    # 3. Verifica arquivos de rotas
    routes_path = backend_path / 'api' / 'admin' / 'routes'
    if routes_path.exists():
        route_files = list(routes_path.glob('*.py'))
        print(f"\n📁 Verificando {len(route_files)} arquivos de rotas...")
        
        for route_file in route_files:
            if route_file.name == '__init__.py':
                continue
            
            valid, error = check_import_syntax(route_file)
            if not valid:
                issues.append(('WARNING', f'Erro de sintaxe em {route_file.name}: {error}', str(route_file)))
            else:
                # Verifica se exporta 'router'
                with open(route_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'router =' not in content and 'router=' not in content:
                        issues.append(('WARNING', f'{route_file.name} não exporta "router"', str(route_file)))
    
    # 4. Verifica duplicações
    print("\n🔎 Verificando importações duplicadas...")
    with open(admin_init, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        seen_imports = {}
        for i, line in enumerate(lines, 1):
            if 'from src.api.admin.routes' in line or 'import router' in line:
                # Normaliza linha
                normalized = line.strip().replace(' ', '')
                if normalized in seen_imports:
                    issues.append(('WARNING', f'Importação duplicada na linha {i}: {line.strip()}', str(admin_init)))
                seen_imports[normalized] = i
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DA AUDITORIA")
    print("="*60)
    
    critical = [i for i in issues if i[0] == 'CRITICAL']
    errors = [i for i in issues if i[0] == 'ERROR']
    warnings = [i for i in issues if i[0] == 'WARNING']
    
    print(f"\n🔴 Críticos: {len(critical)}")
    for issue in critical:
        print(f"   - {issue[1]}")
    
    print(f"\n🟠 Erros: {len(errors)}")
    for issue in errors[:10]:  # Mostra apenas os 10 primeiros
        print(f"   - {issue[1]}")
    if len(errors) > 10:
        print(f"   ... e mais {len(errors) - 10} erros")
    
    print(f"\n🟡 Avisos: {len(warnings)}")
    for issue in warnings[:5]:  # Mostra apenas os 5 primeiros
        print(f"   - {issue[1]}")
    if len(warnings) > 5:
        print(f"   ... e mais {len(warnings) - 5} avisos")
    
    return issues

if __name__ == '__main__':
    issues = audit_backend()
    
    if issues:
        critical_count = len([i for i in issues if i[0] == 'CRITICAL'])
        if critical_count > 0:
            print(f"\n❌ Auditoria falhou com {critical_count} problemas críticos")
            sys.exit(1)
        else:
            print(f"\n⚠️ Auditoria concluída com avisos")
            sys.exit(0)
    else:
        print(f"\n✅ Auditoria concluída sem problemas")
        sys.exit(0)

