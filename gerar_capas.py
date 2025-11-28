#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para pré-gerar as capas do fotolivro.

Gera as imagens de:
- Capa principal
- Subcapas de cada ano
- Contra capa

As imagens são salvas na pasta raiz para uso no preview e no PDF.
"""

import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import numpy as np
from playwright.sync_api import sync_playwright

# Importar funções do fotolivro.py
sys.path.insert(0, str(Path(__file__).parent))
from fotolivro import (
    PASTAS_ANOS, encontrar_pasta_ano, listar_imagens,
    TITULOS_ANOS, TITULO_CAPA, SUBTITULO_CAPA, PERIODO_CAPA,
    A4_LARGURA_MM, A4_ALTURA_MM
)

# Resolução das capas (300 DPI para impressão)
DPI = 300
LARGURA_PX = int(A4_LARGURA_MM * DPI / 25.4)
ALTURA_PX = int(A4_ALTURA_MM * DPI / 25.4)


def criar_mosaico(fotos_paths, largura, altura):
    """
    Cria um mosaico de miniaturas de todas as fotos.
    As fotos são repetidas ciclicamente para preencher toda a imagem.
    """
    if not fotos_paths:
        return Image.new('RGB', (largura, altura), 'white')
    
    num_fotos = len(fotos_paths)
    cols = int(np.ceil(np.sqrt(num_fotos * largura / altura)))
    rows = int(np.ceil(num_fotos / cols))
    
    thumb_w = largura // cols
    thumb_h = altura // rows
    
    # Total de células no grid
    total_celulas = cols * rows
    
    mosaico = Image.new('RGB', (largura, altura), 'black')
    
    # Preencher todas as células, repetindo fotos ciclicamente se necessário
    for i in range(total_celulas):
        # Usar módulo para repetir fotos do começo quando acabarem
        foto_path = fotos_paths[i % num_fotos]
        
        row = i // cols
        col = i % cols
        
        try:
            with Image.open(foto_path) as img:
                img_ratio = img.width / img.height
                cell_ratio = thumb_w / thumb_h
                
                if img_ratio > cell_ratio:
                    new_h = thumb_h
                    new_w = int(new_h * img_ratio)
                else:
                    new_w = thumb_w
                    new_h = int(new_w / img_ratio)
                
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                left = (new_w - thumb_w) // 2
                top = (new_h - thumb_h) // 2
                img_cropped = img_resized.crop((left, top, left + thumb_w, top + thumb_h))
                
                if img_cropped.mode != 'RGB':
                    img_cropped = img_cropped.convert('RGB')
                
                x = col * thumb_w
                y = row * thumb_h
                mosaico.paste(img_cropped, (x, y))
        except Exception as e:
            print(f"  Aviso: Erro ao processar {foto_path}: {e}")
    
    return mosaico


def aplicar_filtro_capa(img):
    """
    Aplica filtro P&B e escurece a imagem para a capa.
    """
    # Converter para escala de cinza
    img_gray = img.convert('L')
    
    # Reduzir brilho
    enhancer = ImageEnhance.Brightness(img_gray)
    img_dark = enhancer.enhance(0.4)
    
    # Reduzir contraste
    enhancer = ImageEnhance.Contrast(img_dark)
    img_final = enhancer.enhance(0.7)
    
    # Converter de volta para RGB
    return img_final.convert('RGB')


def desenhar_texto_capa(img, titulo, subtitulo, periodo):
    """
    Desenha o texto na capa principal.
    """
    draw = ImageDraw.Draw(img)
    
    # Tentar carregar fontes do sistema (fontes divertidas estilo escola)
    try:
        fonte_titulo = ImageFont.truetype("/System/Library/Fonts/Supplemental/Chalkduster.ttf", 180)
        fonte_subtitulo = ImageFont.truetype("/System/Library/Fonts/Supplemental/Chalkboard.ttc", 100)
        fonte_periodo = ImageFont.truetype("/System/Library/Fonts/Supplemental/Chalkboard.ttc", 90)
    except:
        try:
            fonte_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 180)
            fonte_subtitulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 100)
            fonte_periodo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 90)
        except:
            fonte_titulo = ImageFont.load_default()
            fonte_subtitulo = ImageFont.load_default()
            fonte_periodo = ImageFont.load_default()
    
    # Posições
    centro_x = img.width // 2
    centro_y = img.height // 2
    
    # Cor amarela para títulos
    cor_amarela = '#FFD700'
    
    # Título (mais acima para dar espaço)
    bbox_titulo = draw.textbbox((0, 0), titulo, font=fonte_titulo)
    altura_titulo = bbox_titulo[3] - bbox_titulo[1]
    x = centro_x - (bbox_titulo[2] - bbox_titulo[0]) // 2
    y = centro_y - altura_titulo - 80
    draw.text((x, y), titulo, fill=cor_amarela, font=fonte_titulo)
    
    # Subtítulo (no centro)
    bbox_sub = draw.textbbox((0, 0), subtitulo, font=fonte_subtitulo)
    altura_sub = bbox_sub[3] - bbox_sub[1]
    x = centro_x - (bbox_sub[2] - bbox_sub[0]) // 2
    y = centro_y + 60
    draw.text((x, y), subtitulo, fill=cor_amarela, font=fonte_subtitulo)
    
    # Período (mais abaixo)
    bbox_per = draw.textbbox((0, 0), periodo, font=fonte_periodo)
    x = centro_x - (bbox_per[2] - bbox_per[0]) // 2
    y = centro_y + 60 + altura_sub + 80
    draw.text((x, y), periodo, fill=(220, 220, 220), font=fonte_periodo)
    
    return img


def desenhar_texto_subcapa(img, titulo, ano):
    """
    Desenha o texto na subcapa de um ano.
    """
    draw = ImageDraw.Draw(img)
    
    # Fontes divertidas estilo escola
    try:
        fonte_titulo = ImageFont.truetype("/System/Library/Fonts/Supplemental/Chalkduster.ttf", 200)
        fonte_ano = ImageFont.truetype("/System/Library/Fonts/Supplemental/Chalkboard.ttc", 120)
    except:
        try:
            fonte_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 200)
            fonte_ano = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 120)
        except:
            fonte_titulo = ImageFont.load_default()
            fonte_ano = ImageFont.load_default()
    
    centro_x = img.width // 2
    centro_y = img.height // 2
    
    # Cor amarela para títulos
    cor_amarela = '#FFD700'
    
    # Título (mais acima para dar espaço)
    bbox_titulo = draw.textbbox((0, 0), titulo, font=fonte_titulo)
    altura_titulo = bbox_titulo[3] - bbox_titulo[1]
    x = centro_x - (bbox_titulo[2] - bbox_titulo[0]) // 2
    y = centro_y - altura_titulo - 40
    draw.text((x, y), titulo, fill=cor_amarela, font=fonte_titulo)
    
    # Ano (mais abaixo)
    texto_ano = f"~ {ano}"
    bbox_ano = draw.textbbox((0, 0), texto_ano, font=fonte_ano)
    x = centro_x - (bbox_ano[2] - bbox_ano[0]) // 2
    y = centro_y + 100
    draw.text((x, y), texto_ano, fill=(220, 220, 220), font=fonte_ano)
    
    return img


def criar_contra_capa():
    """
    Cria a contra capa usando HTML para melhor formatação e suporte a emojis.
    """
    # HTML da contra capa
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap');
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                width: 3507px;
                height: 2480px;
                background: white;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                font-family: 'Patrick Hand', 'Chalkboard', 'Comic Sans MS', cursive;
                color: #444;
                padding: 150px;
            }
            
            .dedicatoria {
                text-align: center;
                max-width: 2800px;
                line-height: 1.7;
            }
            
            .dedicatoria p {
                font-size: 58px;
                margin-bottom: 45px;
            }
            
            .dedicatoria p.destaque {
                font-size: 64px;
                font-weight: bold;
                color: #333;
            }
            
            .dedicatoria p.assinatura {
                font-size: 54px;
                font-style: italic;
                margin-top: 30px;
            }
            
            .dedicatoria p.local {
                font-size: 48px;
                color: #666;
                margin-top: 20px;
            }
            
            .emojis {
                font-size: 80px;
                margin-top: 60px;
                letter-spacing: 15px;
            }
        </style>
    </head>
    <body>
        <div class="dedicatoria">
            <p class="destaque">Querido filho Bruno, parabéns por essa conquista tão especial.</p>
            
            <p>Quanta coisa vivemos juntos nesses 5 anos de Infantil, não é mesmo?</p>
            
            <p>Você iniciou na escola, começou a falar, a escrever, aprendeu a compartilhar as coisas, a ter amigos, aprendeu a andar de bike (sem rodinhas!) e até a dançar! E o mais importante: aprendeu sobre a casinha mental, sobre os pensamentos e a realizar muitas superações por conta própria. Estamos muito orgulhosos de você, meu amor!</p>
            
            <p class="destaque">Nós te amamos muito!</p>
            
            <p class="assinatura">Um "abraço de família" da Mamãe Aline, Papai Felipe e Mana Elis.</p>
            
            <p class="local">Florianópolis, novembro de 2025.</p>
            
            <p class="emojis">🎓📚🧠💭⛰️🚲👦🕺👨‍👩‍👧‍👦❤️✨</p>
        </div>
    </body>
    </html>
    """
    
    # Criar arquivo HTML temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        html_path = f.name
    
    # Renderizar HTML para imagem usando Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': LARGURA_PX, 'height': ALTURA_PX})
        page.goto(f'file://{html_path}')
        page.wait_for_load_state('networkidle')
        
        # Capturar screenshot
        screenshot_bytes = page.screenshot(type='png')
        browser.close()
    
    # Remover arquivo temporário
    Path(html_path).unlink()
    
    # Converter para PIL Image
    from io import BytesIO
    img = Image.open(BytesIO(screenshot_bytes))
    
    # Converter para RGB (remover canal alpha)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    return img


def gerar_capas(pasta_raiz):
    """
    Gera todas as capas e salva na pasta raiz.
    """
    pasta_raiz = Path(pasta_raiz)
    pasta_capas = pasta_raiz / "_capas"
    pasta_capas.mkdir(exist_ok=True)
    
    print("Gerando capas do fotolivro...")
    print(f"Resolução: {LARGURA_PX}x{ALTURA_PX} px ({DPI} DPI)")
    
    # Coletar todas as fotos
    todas_fotos = []
    fotos_por_ano = {}
    
    for nome_pasta in PASTAS_ANOS:
        pasta = encontrar_pasta_ano(pasta_raiz, nome_pasta)
        if pasta is None:
            continue
        
        caminhos = listar_imagens(pasta)
        if caminhos:
            fotos_por_ano[nome_pasta] = caminhos
            todas_fotos.extend(caminhos)
    
    print(f"Total de fotos: {len(todas_fotos)}")
    
    # 1. Capa principal
    print("\n1. Gerando capa principal...")
    mosaico = criar_mosaico(todas_fotos, LARGURA_PX, ALTURA_PX)
    mosaico = aplicar_filtro_capa(mosaico)
    capa = desenhar_texto_capa(mosaico, TITULO_CAPA, SUBTITULO_CAPA, PERIODO_CAPA)
    capa_path = pasta_capas / "capa.jpg"
    capa.save(capa_path, 'JPEG', quality=95)
    print(f"   ✓ Salvo: {capa_path}")
    
    # 2. Subcapas por ano
    print("\n2. Gerando subcapas dos anos...")
    for nome_pasta, fotos in fotos_por_ano.items():
        titulo, ano = TITULOS_ANOS.get(nome_pasta, (nome_pasta, ""))
        print(f"   {titulo}...")
        
        mosaico = criar_mosaico(fotos, LARGURA_PX, ALTURA_PX)
        mosaico = aplicar_filtro_capa(mosaico)
        subcapa = desenhar_texto_subcapa(mosaico, titulo, ano)
        
        subcapa_path = pasta_capas / f"subcapa_{nome_pasta.lower()}.jpg"
        subcapa.save(subcapa_path, 'JPEG', quality=95)
        print(f"   ✓ Salvo: {subcapa_path}")
    
    # 3. Contra capa
    print("\n3. Gerando contra capa...")
    contra_capa = criar_contra_capa()
    contra_capa_path = pasta_capas / "contra_capa.jpg"
    contra_capa.save(contra_capa_path, 'JPEG', quality=95)
    print(f"   ✓ Salvo: {contra_capa_path}")
    
    print(f"\n✓ Capas geradas em: {pasta_capas}")
    return pasta_capas


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python gerar_capas.py <pasta_raiz>")
        print("\nExemplo:")
        print("  python gerar_capas.py ./fotos_bruno")
        sys.exit(1)
    
    pasta_raiz = Path(sys.argv[1])
    
    if not pasta_raiz.exists():
        print(f"ERRO: Pasta não encontrada: {pasta_raiz}")
        sys.exit(1)
    
    gerar_capas(pasta_raiz)

