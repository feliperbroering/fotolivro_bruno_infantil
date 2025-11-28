#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderizador de PDF do Fotolivro

Este módulo renderiza o fotolivro em PDF baseado no schema definido.
O schema é a fonte única de verdade - o PDF é gerado exatamente como definido.

EXECUÇÃO:
    python pdf_renderer.py <pasta_raiz> [arquivo_saida.pdf]

Exemplo:
    python pdf_renderer.py ./fotos_bruno ./meu_fotolivro.pdf
"""

import sys
from pathlib import Path
from typing import Tuple, List
from io import BytesIO

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

from schema_manager import SchemaManager, PaginaSchema, FotoSchema


# Dimensões A4 em paisagem (297mm x 210mm)
A4_LARGURA_MM = 297
A4_ALTURA_MM = 210

# Margens (em milímetros)
MARGEM_EXTERNA_MM = 10  # 1 cm
MARGEM_LOMBADA_MM = 15  # 1.5 cm
ESPACO_ENTRE_FOTOS_MM = 5  # 0.5 cm


def mm_to_points(mm_value: float) -> float:
    """Converte milímetros para points."""
    return mm_value * 72.0 / 25.4


class PDFRenderer:
    """Renderiza o fotolivro em PDF baseado no schema."""
    
    def __init__(self, pasta_raiz: Path, arquivo_saida: Path):
        self.pasta_raiz = Path(pasta_raiz)
        self.arquivo_saida = Path(arquivo_saida)
        
        # Dimensões da página em points
        self.largura_pagina = mm_to_points(A4_LARGURA_MM)
        self.altura_pagina = mm_to_points(A4_ALTURA_MM)
        
        # Margens em points
        self.margem_externa = mm_to_points(MARGEM_EXTERNA_MM)
        self.margem_lombada = mm_to_points(MARGEM_LOMBADA_MM)
        self.espaco_entre_fotos = mm_to_points(ESPACO_ENTRE_FOTOS_MM)
        
        self.canvas = None
        self.numero_pagina = 0
    
    def renderizar(self, schema: SchemaManager) -> bool:
        """Renderiza o PDF completo baseado no schema."""
        try:
            self.canvas = canvas.Canvas(
                str(self.arquivo_saida),
                pagesize=(self.largura_pagina, self.altura_pagina)
            )
        except Exception as e:
            print(f"ERRO: Não foi possível criar o arquivo PDF: {e}")
            return False
        
        print(f"Renderizando {schema.total_paginas()} páginas...")
        
        for i, pagina in enumerate(schema.paginas):
            self.numero_pagina = i + 1
            
            if pagina.tipo == 'capa':
                self._renderizar_capa(pagina)
            elif pagina.tipo == 'subcapa':
                self._renderizar_subcapa(pagina)
            elif pagina.tipo == 'contra_capa':
                self._renderizar_contra_capa(pagina)
            elif pagina.tipo == 'conteudo':
                self._renderizar_conteudo(pagina)
        
        try:
            self.canvas.save()
        except Exception as e:
            print(f"ERRO: Não foi possível salvar o PDF: {e}")
            return False
        
        print(f"\n✓ PDF gerado com sucesso!")
        print(f"  Total de páginas: {schema.total_paginas()}")
        print(f"  Arquivo: {self.arquivo_saida.absolute()}")
        
        return True
    
    def _renderizar_capa(self, pagina: PaginaSchema):
        """Renderiza a página de capa."""
        if pagina.imagem:
            img_path = self.pasta_raiz / pagina.imagem
            if img_path.exists():
                self.canvas.drawImage(
                    str(img_path),
                    0, 0,
                    width=self.largura_pagina,
                    height=self.altura_pagina,
                    preserveAspectRatio=False
                )
        
        self.canvas.showPage()
    
    def _renderizar_subcapa(self, pagina: PaginaSchema):
        """Renderiza uma subcapa de ano."""
        if pagina.imagem:
            img_path = self.pasta_raiz / pagina.imagem
            if img_path.exists():
                self.canvas.drawImage(
                    str(img_path),
                    0, 0,
                    width=self.largura_pagina,
                    height=self.altura_pagina,
                    preserveAspectRatio=False
                )
        
        self.canvas.showPage()
    
    def _renderizar_contra_capa(self, pagina: PaginaSchema):
        """Renderiza a contra capa."""
        if pagina.imagem:
            img_path = self.pasta_raiz / pagina.imagem
            if img_path.exists():
                self.canvas.drawImage(
                    str(img_path),
                    0, 0,
                    width=self.largura_pagina,
                    height=self.altura_pagina,
                    preserveAspectRatio=False
                )
        else:
            # Fallback: texto simples
            self.canvas.setFillColor('black')
            self.canvas.setFont('Helvetica-Bold', 32)
            texto1 = pagina.titulo
            texto1_w = self.canvas.stringWidth(texto1, 'Helvetica-Bold', 32)
            self.canvas.drawString(
                (self.largura_pagina - texto1_w) / 2,
                self.altura_pagina * 0.55,
                texto1
            )
            
            self.canvas.setFont('Helvetica', 24)
            texto2 = pagina.subtitulo
            texto2_w = self.canvas.stringWidth(texto2, 'Helvetica', 24)
            self.canvas.drawString(
                (self.largura_pagina - texto2_w) / 2,
                self.altura_pagina * 0.45,
                texto2
            )
        
        self.canvas.showPage()
    
    def _renderizar_conteudo(self, pagina: PaginaSchema):
        """Renderiza uma página de conteúdo com fotos."""
        pagina_impar = (self.numero_pagina % 2 == 1)
        area_util = self._calcular_area_util(pagina_impar)
        
        # Obter boxes do layout
        boxes = self._calcular_boxes_layout(pagina.layout, area_util)
        
        # Renderizar cada foto
        for foto in pagina.fotos:
            if foto.slot_index < len(boxes):
                box = boxes[foto.slot_index]
                self._renderizar_foto(foto, box)
        
        self.canvas.showPage()
    
    def _calcular_area_util(self, pagina_impar: bool) -> Tuple[float, float, float, float]:
        """Calcula a área útil da página (sem margens)."""
        if pagina_impar:
            margem_esquerda = self.margem_lombada
            margem_direita = self.margem_externa
        else:
            margem_esquerda = self.margem_externa
            margem_direita = self.margem_lombada
        
        x = margem_esquerda
        y = self.margem_externa
        largura = self.largura_pagina - margem_esquerda - margem_direita
        altura = self.altura_pagina - self.margem_externa * 2
        
        return (x, y, largura, altura)
    
    def _calcular_boxes_layout(self, layout: str, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """Calcula as boxes (slots) para cada layout."""
        x, y, largura, altura = area_util
        esp = self.espaco_entre_fotos
        
        if layout == 'L1':
            return [(x, y, largura, altura)]
        
        elif layout == 'L2H':
            # 2 fotos lado a lado
            w = (largura - esp) / 2
            return [
                (x, y, w, altura),
                (x + w + esp, y, w, altura)
            ]
        
        elif layout == 'L2V':
            # 2 fotos empilhadas
            h = (altura - esp) / 2
            return [
                (x, y + h + esp, largura, h),
                (x, y, largura, h)
            ]
        
        elif layout == 'L3A':
            # 2 em cima, 1 embaixo
            h = (altura - esp) / 2
            w = (largura - esp) / 2
            return [
                (x, y + h + esp, w, h),
                (x + w + esp, y + h + esp, w, h),
                (x, y, largura, h)
            ]
        
        elif layout == 'L3B':
            # 1 em cima, 2 embaixo
            h = (altura - esp) / 2
            w = (largura - esp) / 2
            return [
                (x, y + h + esp, largura, h),
                (x, y, w, h),
                (x + w + esp, y, w, h)
            ]
        
        elif layout == 'L3C':
            # 1 vertical à direita, 2 horizontais à esquerda
            w_esq = (largura - esp) * 0.60
            w_dir = (largura - esp) * 0.40
            h = (altura - esp) / 2
            return [
                (x + w_esq + esp, y, w_dir, altura),  # Vertical à direita
                (x, y + h + esp, w_esq, h),  # Horizontal superior
                (x, y, w_esq, h)  # Horizontal inferior
            ]
        
        elif layout == 'L3D':
            # 1 horizontal em cima, 2 horizontais embaixo
            h = (altura - esp) / 2
            w = (largura - esp) / 2
            return [
                (x, y + h + esp, largura, h),
                (x, y, w, h),
                (x + w + esp, y, w, h)
            ]
        
        elif layout == 'L4':
            # Grid 2x2
            w = (largura - esp) / 2
            h = (altura - esp) / 2
            return [
                (x, y + h + esp, w, h),
                (x + w + esp, y + h + esp, w, h),
                (x, y, w, h),
                (x + w + esp, y, w, h)
            ]
        
        return [(x, y, largura, altura)]
    
    def _renderizar_foto(self, foto: FotoSchema, box: Tuple[float, float, float, float]):
        """Renderiza uma foto em seu slot com os ajustes definidos."""
        x_box, y_box, w_box, h_box = box
        
        try:
            img_path = self.pasta_raiz / foto.caminho
            
            with Image.open(img_path) as img:
                img_w, img_h = img.size
                
                # Calcular escala base para "cover" (preencher slot)
                scale_x = w_box / img_w
                scale_y = h_box / img_h
                base_cover_scale = max(scale_x, scale_y)
                
                # Escala mínima para "contain" (mostrar toda imagem)
                base_contain_scale = min(scale_x, scale_y)
                
                # Aplicar zoom do usuário
                # zoom 1.0 = cover, zoom < 1 = mostra mais (até contain)
                min_zoom = base_contain_scale / base_cover_scale if base_cover_scale > 0 else 0.3
                effective_zoom = max(min_zoom, foto.zoom)
                final_scale = base_cover_scale * effective_zoom
                
                # Tamanho final da imagem
                display_w = img_w * final_scale
                display_h = img_h * final_scale
                
                # Quanto a imagem excede/falta no slot
                excess_w = display_w - w_box
                excess_h = display_h - h_box
                
                # Posição baseada no pan (0.5 = centralizado)
                # Nota: eixo Y do PDF é invertido em relação ao HTML
                # No HTML: pan_y=0 mostra topo, pan_y=1 mostra base
                # No PDF: Y cresce para cima, então invertemos
                offset_x = -excess_w * foto.pan_x
                offset_y = -excess_h * (1 - foto.pan_y)
                
                # Posição final da imagem
                img_x = x_box + offset_x
                img_y = y_box + offset_y
                
                # Se a imagem não cobre todo o slot, precisamos de clipping
                # Salvar estado do canvas para aplicar clip
                self.canvas.saveState()
                
                # Criar área de clipping (o slot)
                clip_path = self.canvas.beginPath()
                clip_path.rect(x_box, y_box, w_box, h_box)
                self.canvas.clipPath(clip_path, stroke=0, fill=0)
                
                # Converter imagem para buffer
                img_buffer = BytesIO()
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(img_buffer, format='JPEG', quality=95)
                img_buffer.seek(0)
                
                # Desenhar imagem na posição calculada
                self.canvas.drawImage(
                    ImageReader(img_buffer),
                    img_x, img_y,
                    width=display_w,
                    height=display_h,
                    preserveAspectRatio=False,
                    mask='auto'
                )
                
                # Restaurar estado do canvas
                self.canvas.restoreState()
        
        except Exception as e:
            print(f"AVISO: Erro ao renderizar {foto.caminho}: {e}")
    
    def _calcular_crop(self, img_largura: int, img_altura: int,
                       slot_largura: float, slot_altura: float,
                       pan_x: float, pan_y: float, zoom: float) -> Tuple[int, int, int, int]:
        """Calcula o crop baseado nos ajustes de pan/zoom."""
        ratio_slot = slot_largura / slot_altura
        ratio_img = img_largura / img_altura
        
        # Calcular dimensões do crop base (modo cover)
        if ratio_img > ratio_slot:
            crop_h = img_altura
            crop_w = int(crop_h * ratio_slot)
        else:
            crop_w = img_largura
            crop_h = int(crop_w / ratio_slot)
        
        # Aplicar zoom (reduz o tamanho do crop)
        crop_w = int(crop_w / zoom)
        crop_h = int(crop_h / zoom)
        
        # Garantir que o crop não seja maior que a imagem
        crop_w = min(crop_w, img_largura)
        crop_h = min(crop_h, img_altura)
        
        # Calcular posição baseada no pan
        max_x = img_largura - crop_w
        max_y = img_altura - crop_h
        
        crop_x = int(pan_x * max_x)
        crop_y = int(pan_y * max_y)
        
        # Garantir bounds
        crop_x = max(0, min(crop_x, max_x))
        crop_y = max(0, min(crop_y, max_y))
        
        return (crop_x, crop_y, crop_w, crop_h)


def main():
    """Função principal para execução via linha de comando."""
    if len(sys.argv) < 2:
        print("Uso: python pdf_renderer.py <pasta_raiz> [arquivo_saida.pdf]")
        print("\nExemplo:")
        print("  python pdf_renderer.py ./fotos_bruno")
        print("  python pdf_renderer.py ./fotos_bruno ./meu_fotolivro.pdf")
        sys.exit(1)
    
    pasta_raiz = Path(sys.argv[1]).resolve()
    
    if len(sys.argv) >= 3:
        arquivo_saida = Path(sys.argv[2])
    else:
        arquivo_saida = pasta_raiz / "fotolivro_final.pdf"
    
    # Carregar schema
    schema = SchemaManager(pasta_raiz)
    if not schema.carregar():
        print("ERRO: Schema não encontrado. Execute o preview primeiro para gerar o schema.")
        print("  python preview_server.py", pasta_raiz)
        sys.exit(1)
    
    # Renderizar PDF
    renderer = PDFRenderer(pasta_raiz, arquivo_saida)
    sucesso = renderer.renderizar(schema)
    
    if not sucesso:
        sys.exit(1)


if __name__ == "__main__":
    main()

