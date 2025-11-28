#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor de Preview do Fotolivro

Este servidor permite visualizar e ajustar o enquadramento das fotos
antes de gerar o PDF final.

EXECUÇÃO:
    python preview_server.py <pasta_raiz>

Exemplo:
    python preview_server.py ./fotos_bruno

INSTALAÇÃO DAS DEPENDÊNCIAS:
    pip install flask pillow
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory

# Importar gerenciador de schema
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_manager import SchemaManager


app = Flask(__name__, static_folder='static', template_folder='templates')

# Variáveis globais
pasta_raiz = None
schema_manager = None


def inicializar_schema():
    """Inicializa ou carrega o schema do fotolivro."""
    global schema_manager
    
    schema_manager = SchemaManager(pasta_raiz)
    
    if not schema_manager.carregar():
        print("Schema não encontrado. Gerando schema inicial...")
        schema_manager.gerar_schema_inicial()
        schema_manager.migrar_ajustes_antigos()
        print(f"Schema gerado com {schema_manager.total_paginas()} páginas")
    else:
        print(f"Schema carregado com {schema_manager.total_paginas()} páginas")


@app.route('/')
def index():
    """Página principal com o preview do fotolivro."""
    return render_template('preview.html')


@app.route('/api/fotolivro')
def api_fotolivro():
    """Retorna a estrutura completa do fotolivro baseada no schema."""
    return jsonify(schema_manager.to_dict())


@app.route('/api/atualizar_foto', methods=['POST'])
def api_atualizar_foto():
    """Atualiza os ajustes de uma foto específica."""
    data = request.json
    caminho = data.get('caminho')
    
    schema_manager.atualizar_foto(
        caminho=caminho,
        pan_x=data.get('pan_x'),
        pan_y=data.get('pan_y'),
        zoom=data.get('zoom'),
        slot_tipo=data.get('slot_tipo')
    )
    
    schema_manager.salvar()
    return jsonify({'success': True})


@app.route('/api/atualizar_layout', methods=['POST'])
def api_atualizar_layout():
    """Atualiza o layout de uma página."""
    data = request.json
    indice = data.get('indice_pagina')
    layout = data.get('layout')
    
    schema_manager.atualizar_layout_pagina(indice, layout)
    schema_manager.salvar()
    
    return jsonify({'success': True})


@app.route('/api/mudar_layout_pagina', methods=['POST'])
def api_mudar_layout_pagina():
    """
    Muda o layout de uma página redistribuindo fotos apenas no capítulo atual.
    - Não altera páginas anteriores
    - Não altera outros capítulos
    - Fotos excedentes vão para o final do capítulo
    """
    data = request.json
    indice_pagina = data.get('indice_pagina')
    novo_layout = data.get('novo_layout')
    
    if indice_pagina is None or novo_layout is None:
        return jsonify({'success': False, 'mensagem': 'Parâmetros inválidos'})
    
    # Calcular número de fotos do novo layout
    fotos_por_layout = {
        'L1': 1, 'L2H': 2, 'L2V': 2,
        'L3A': 3, 'L3B': 3, 'L3C': 3, 'L3D': 3,
        'L4': 4
    }
    num_fotos_necessarias = fotos_por_layout.get(novo_layout, 1)
    
    # Encontrar limites do capítulo atual
    inicio_capitulo, fim_capitulo = schema_manager.encontrar_limites_capitulo(indice_pagina)
    
    if inicio_capitulo is None:
        return jsonify({'success': False, 'mensagem': 'Página não encontrada'})
    
    # Redistribuir fotos no capítulo
    sucesso = schema_manager.redistribuir_fotos_capitulo(
        indice_pagina, novo_layout, num_fotos_necessarias,
        inicio_capitulo, fim_capitulo
    )
    
    if sucesso:
        schema_manager.salvar()
        return jsonify({
            'success': True,
            'paginas': schema_manager.to_dict()['paginas'],
            'total_paginas': schema_manager.total_paginas()
        })
    else:
        return jsonify({'success': False, 'mensagem': 'Não foi possível redistribuir fotos'})


@app.route('/api/reorganizar_pagina', methods=['POST'])
def api_reorganizar_pagina():
    """Reorganiza uma página com novo layout e configuração de fotos."""
    data = request.json
    indice = data.get('indice_pagina')
    layout = data.get('layout')
    fotos = data.get('fotos', [])
    
    schema_manager.reorganizar_pagina(indice, layout, fotos)
    schema_manager.salvar()
    
    return jsonify({'success': True})


@app.route('/api/regenerar_schema', methods=['POST'])
def api_regenerar_schema():
    """Regenera o schema do zero (útil após adicionar/remover fotos)."""
    schema_manager.gerar_schema_inicial()
    schema_manager.migrar_ajustes_antigos()
    
    return jsonify({
        'success': True,
        'total_paginas': schema_manager.total_paginas()
    })


@app.route('/api/ajustes', methods=['GET', 'POST'])
def api_ajustes():
    """Compatibilidade: GET retorna ajustes, POST salva ajustes."""
    if request.method == 'GET':
        # Extrair ajustes do schema
        ajustes = {}
        for pagina in schema_manager.paginas:
            for foto in pagina.fotos:
                ajustes[foto.caminho] = {
                    'pan_x': foto.pan_x,
                    'pan_y': foto.pan_y,
                    'zoom': foto.zoom,
                    'slot_tipo': foto.slot_tipo
                }
        return jsonify({'ajustes': ajustes, 'layouts': {}})
    else:
        # POST: salvar ajustes
        data = request.json
        ajustes = data.get('ajustes', {})
        layouts = data.get('layouts', {})
        
        # Atualizar ajustes das fotos
        for caminho, aj in ajustes.items():
            schema_manager.atualizar_foto(
                caminho=caminho,
                pan_x=aj.get('pan_x'),
                pan_y=aj.get('pan_y'),
                zoom=aj.get('zoom'),
                slot_tipo=aj.get('slot_tipo')
            )
        
        # Atualizar layouts das páginas
        for indice_str, layout in layouts.items():
            try:
                indice = int(indice_str)
                schema_manager.atualizar_layout_pagina(indice, layout)
            except (ValueError, TypeError):
                pass
        
        schema_manager.salvar()
        return jsonify({'success': True})


@app.route('/foto/<path:foto_path>')
def servir_foto(foto_path):
    """Serve uma foto do diretório raiz."""
    return send_from_directory(pasta_raiz, foto_path)


@app.route('/api/gerar_pdf', methods=['POST'])
def api_gerar_pdf():
    """Gera o PDF final baseado no schema."""
    from pdf_renderer import PDFRenderer
    
    arquivo_saida = pasta_raiz / "fotolivro_final.pdf"
    renderer = PDFRenderer(pasta_raiz, arquivo_saida)
    
    sucesso = renderer.renderizar(schema_manager)
    
    if sucesso:
        return jsonify({
            'success': True,
            'arquivo': str(arquivo_saida),
            'mensagem': f'PDF gerado: {arquivo_saida}'
        })
    else:
        return jsonify({
            'success': False,
            'mensagem': 'Erro ao gerar PDF'
        })


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python preview_server.py <pasta_raiz>")
        print("\nExemplo:")
        print("  python preview_server.py ./fotos_bruno")
        sys.exit(1)
    
    pasta_raiz = Path(sys.argv[1]).resolve()
    
    if not pasta_raiz.exists():
        print(f"ERRO: Pasta não encontrada: {pasta_raiz}")
        sys.exit(1)
    
    print(f"Pasta raiz: {pasta_raiz}")
    inicializar_schema()
    
    print("\n" + "=" * 50)
    print("🔍 Preview do Fotolivro")
    print("=" * 50)
    print(f"\nAcesse: http://localhost:5001")
    print("\nPressione Ctrl+C para encerrar")
    print("=" * 50 + "\n")
    
    app.run(debug=True, port=5001, host='127.0.0.1')
