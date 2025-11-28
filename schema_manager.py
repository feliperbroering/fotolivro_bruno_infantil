#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciador de Schema do Fotolivro

Este módulo define e gerencia o schema completo do fotolivro,
que serve como fonte única de verdade para o preview e o PDF.

O schema define:
- Lista de todas as páginas
- Layout de cada página
- Fotos em cada página com seus slots e ajustes
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from PIL import Image

# Constantes
PASTAS_ANOS = ["Infantil1", "Infantil2", "Infantil3", "Infantil4", "Infantil5"]
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

TITULOS_ANOS = {
    "Infantil1": ("Infantil 1", "2021"),
    "Infantil2": ("Infantil 2", "2022"),
    "Infantil3": ("Infantil 3", "2023"),
    "Infantil4": ("Infantil 4", "2024"),
    "Infantil5": ("Infantil 5", "2025"),
}

TITULO_CAPA = "Bruno Sereia Broering"
SUBTITULO_CAPA = "Momentos no Infantil 1 ao 5"
PERIODO_CAPA = "2021 ~ 2025"


def classificar_imagem(largura: int, altura: int) -> str:
    """Classifica uma imagem como paisagem, retrato ou quadrada."""
    if largura == 0 or altura == 0:
        return 'paisagem'
    
    ratio = largura / altura
    
    if 0.9 <= ratio <= 1.1:
        return 'quadrada'
    elif ratio > 1:
        return 'paisagem'
    else:
        return 'retrato'


def encontrar_pasta_ano(diretorio_raiz: Path, nome_pasta: str) -> Optional[Path]:
    """Encontra uma pasta de ano no diretório raiz (case-insensitive)."""
    diretorio_raiz = Path(diretorio_raiz)
    if not diretorio_raiz.exists():
        return None
    
    for item in diretorio_raiz.iterdir():
        if item.is_dir() and item.name.lower() == nome_pasta.lower():
            return item
    
    return None


def listar_imagens(pasta: Path) -> List[Path]:
    """Lista todas as imagens válidas em uma pasta, ordenadas por nome."""
    imagens = []
    if not pasta.exists() or not pasta.is_dir():
        return imagens
    
    for arquivo in sorted(pasta.iterdir()):
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_IMAGEM:
            imagens.append(arquivo)
    
    return imagens


@dataclass
class FotoSchema:
    """Schema de uma foto em um slot."""
    caminho: str  # Caminho relativo da foto
    largura: int  # Largura original em pixels
    altura: int  # Altura original em pixels
    orientacao: str  # 'paisagem', 'retrato', 'quadrada'
    slot_index: int  # Índice do slot na página (0, 1, 2, 3)
    pan_x: float = 0.5  # Posição horizontal do pan (0-1)
    pan_y: float = 0.5  # Posição vertical do pan (0-1)
    zoom: float = 1.0  # Nível de zoom
    slot_tipo: str = 'auto'  # Tipo de slot definido pelo usuário


@dataclass
class PaginaSchema:
    """Schema de uma página do fotolivro."""
    tipo: str  # 'capa', 'subcapa', 'conteudo', 'contra_capa'
    layout: str  # 'L1', 'L2H', 'L2V', 'L3A', 'L3B', 'L3C', 'L3D', 'L4'
    fotos: List[FotoSchema]  # Lista de fotos na página
    # Campos opcionais para capas
    titulo: str = ""
    subtitulo: str = ""
    ano: str = ""
    imagem: str = ""  # Caminho da imagem pré-gerada (para capas)


class SchemaManager:
    """Gerencia o schema do fotolivro."""
    
    def __init__(self, pasta_raiz: Path):
        self.pasta_raiz = Path(pasta_raiz)
        self.schema_path = self.pasta_raiz / "schema_fotolivro.json"
        self.paginas: List[PaginaSchema] = []
    
    def carregar(self) -> bool:
        """Carrega o schema do arquivo JSON."""
        if not self.schema_path.exists():
            return False
        
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.paginas = []
            for pag_data in data.get('paginas', []):
                fotos = []
                for foto_data in pag_data.get('fotos', []):
                    fotos.append(FotoSchema(**foto_data))
                
                pag = PaginaSchema(
                    tipo=pag_data['tipo'],
                    layout=pag_data.get('layout', 'L1'),
                    fotos=fotos,
                    titulo=pag_data.get('titulo', ''),
                    subtitulo=pag_data.get('subtitulo', ''),
                    ano=pag_data.get('ano', ''),
                    imagem=pag_data.get('imagem', '')
                )
                self.paginas.append(pag)
            
            return True
        except Exception as e:
            print(f"Erro ao carregar schema: {e}")
            return False
    
    def salvar(self):
        """Salva o schema no arquivo JSON."""
        data = {
            'versao': '1.0',
            'total_paginas': len(self.paginas),
            'paginas': []
        }
        
        for pag in self.paginas:
            pag_data = {
                'tipo': pag.tipo,
                'layout': pag.layout,
                'fotos': [asdict(f) for f in pag.fotos],
                'titulo': pag.titulo,
                'subtitulo': pag.subtitulo,
                'ano': pag.ano,
                'imagem': pag.imagem
            }
            data['paginas'].append(pag_data)
        
        with open(self.schema_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def gerar_schema_inicial(self):
        """Gera o schema inicial baseado nas fotos existentes."""
        self.paginas = []
        
        # Carregar ajustes antigos para considerar slot_tipos no agrupamento
        ajustes_antigos = self._carregar_ajustes_antigos()
        
        # Capa principal
        capa_img = self.pasta_raiz / "_capas" / "capa.jpg"
        self.paginas.append(PaginaSchema(
            tipo='capa',
            layout='L1',
            fotos=[],
            titulo=TITULO_CAPA,
            subtitulo=SUBTITULO_CAPA,
            ano=PERIODO_CAPA,
            imagem='_capas/capa.jpg' if capa_img.exists() else ''
        ))
        
        # Processar cada ano
        for nome_pasta in PASTAS_ANOS:
            pasta = encontrar_pasta_ano(self.pasta_raiz, nome_pasta)
            if pasta is None:
                continue
            
            caminhos = listar_imagens(pasta)
            if not caminhos:
                continue
            
            # Subcapa do ano
            titulo_ano, ano = TITULOS_ANOS.get(nome_pasta, (nome_pasta, ""))
            subcapa_img = self.pasta_raiz / "_capas" / f"subcapa_{nome_pasta.lower()}.jpg"
            self.paginas.append(PaginaSchema(
                tipo='subcapa',
                layout='L1',
                fotos=[],
                titulo=titulo_ano,
                ano=ano,
                imagem=f'_capas/subcapa_{nome_pasta.lower()}.jpg' if subcapa_img.exists() else ''
            ))
            
            # Carregar informações das fotos
            fotos_info = []
            for caminho in caminhos:
                try:
                    with Image.open(caminho) as img:
                        largura, altura = img.size
                except:
                    largura, altura = 1920, 1080
                
                foto_path = str(caminho.relative_to(self.pasta_raiz))
                orientacao = classificar_imagem(largura, altura)
                
                fotos_info.append({
                    'caminho': foto_path,
                    'largura': largura,
                    'altura': altura,
                    'orientacao': orientacao
                })
            
            # Agrupar fotos em páginas (considerando slot_tipos existentes)
            grupos = self._agrupar_fotos_inicial(fotos_info, ajustes_antigos)
            
            for grupo in grupos:
                layout = self._escolher_layout_inicial(grupo, ajustes_antigos)
                
                fotos_schema = []
                for i, foto in enumerate(grupo):
                    # Usar ajustes existentes se houver
                    aj = ajustes_antigos.get(foto['caminho'], {})
                    
                    fotos_schema.append(FotoSchema(
                        caminho=foto['caminho'],
                        largura=foto['largura'],
                        altura=foto['altura'],
                        orientacao=foto['orientacao'],
                        slot_index=i,
                        pan_x=aj.get('pan_x', 0.5),
                        pan_y=aj.get('pan_y', 0.5),
                        zoom=aj.get('zoom', 1.0),
                        slot_tipo=aj.get('slot_tipo', 'auto')
                    ))
                
                self.paginas.append(PaginaSchema(
                    tipo='conteudo',
                    layout=layout,
                    fotos=fotos_schema
                ))
        
        # Contra capa
        contra_capa_img = self.pasta_raiz / "_capas" / "contra_capa.jpg"
        self.paginas.append(PaginaSchema(
            tipo='contra_capa',
            layout='L1',
            fotos=[],
            titulo='Bruno Sereia Broering',
            subtitulo='Infantil 2021 ~ 2025',
            imagem='_capas/contra_capa.jpg' if contra_capa_img.exists() else ''
        ))
        
        self.salvar()
    
    def _agrupar_fotos_inicial(self, fotos: List[Dict], ajustes: Dict = None) -> List[List[Dict]]:
        """
        Agrupa fotos em páginas considerando slot_tipos definidos.
        
        Args:
            fotos: Lista de dicts com info das fotos
            ajustes: Dict de ajustes existentes (caminho -> {slot_tipo, ...})
        """
        if ajustes is None:
            ajustes = {}
        
        def get_slot_tipo(foto):
            """Obtém slot_tipo de uma foto."""
            return ajustes.get(foto['caminho'], {}).get('slot_tipo', 'auto')
        
        grupos = []
        i = 0
        
        while i < len(fotos):
            foto_atual = fotos[i]
            restantes = len(fotos) - i
            slot_tipo = get_slot_tipo(foto_atual)
            
            # Foto com tipo 'full' vai sozinha
            if slot_tipo == 'full':
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Fotos verticais (fv-l ou fv-r) formam par com próxima
            if slot_tipo in ['fv-l', 'fv-r']:
                if restantes >= 2:
                    proxima = fotos[i + 1]
                    tipo_proxima = get_slot_tipo(proxima)
                    if tipo_proxima in ['fv-l', 'fv-r', 'square', 'auto']:
                        grupos.append([foto_atual, proxima])
                        i += 2
                        continue
                # Sozinha
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Fotos horizontais (fh-t ou fh-b) formam par
            if slot_tipo in ['fh-t', 'fh-b']:
                if restantes >= 2:
                    proxima = fotos[i + 1]
                    tipo_proxima = get_slot_tipo(proxima)
                    if tipo_proxima in ['fh-t', 'fh-b', 'square', 'auto']:
                        grupos.append([foto_atual, proxima])
                        i += 2
                        continue
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Lógica padrão: verificar limite antes de fotos especiais
            def encontrar_limite(inicio, max_fotos):
                limite = 0
                for j in range(inicio, min(inicio + max_fotos, len(fotos))):
                    tipo_j = get_slot_tipo(fotos[j])
                    if tipo_j in ['full', 'fv-l', 'fv-r', 'fh-t', 'fh-b']:
                        break
                    limite += 1
                return limite
            
            max_grupo = encontrar_limite(i, 4)
            
            # Tentar grupo de 4
            if max_grupo >= 4 and restantes >= 4:
                grupos.append(fotos[i:i+4])
                i += 4
                continue
            
            # Tentar grupo de 3
            if max_grupo >= 3 and restantes >= 3:
                proximas_3 = fotos[i:i+3]
                orientacoes = [f['orientacao'] for f in proximas_3]
                paisagem_count = sum(1 for o in orientacoes if o in ['paisagem', 'quadrada'])
                if paisagem_count >= 2:
                    grupos.append(proximas_3)
                    i += 3
                    continue
            
            # Tentar grupo de 2
            if max_grupo >= 2 and restantes >= 2:
                grupos.append(fotos[i:i+2])
                i += 2
                continue
            
            # Foto sozinha
            grupos.append([fotos[i]])
            i += 1
        
        return grupos
    
    def _escolher_layout_inicial(self, fotos: List[Dict], ajustes: Dict = None) -> str:
        """Escolhe o layout inicial para um grupo de fotos."""
        if ajustes is None:
            ajustes = {}
        
        num_fotos = len(fotos)
        
        if num_fotos == 1:
            return 'L1'
        
        elif num_fotos == 2:
            # Verificar tipos de slot
            tipo1 = ajustes.get(fotos[0]['caminho'], {}).get('slot_tipo', 'auto')
            tipo2 = ajustes.get(fotos[1]['caminho'], {}).get('slot_tipo', 'auto')
            
            # Se qualquer uma é vertical, usar L2H
            if tipo1 in ['fv-l', 'fv-r'] or tipo2 in ['fv-l', 'fv-r']:
                return 'L2H'
            
            # Se qualquer uma é horizontal, usar L2V
            if tipo1 in ['fh-t', 'fh-b'] or tipo2 in ['fh-t', 'fh-b']:
                return 'L2V'
            
            # Padrão: lado a lado
            return 'L2H'
        
        elif num_fotos == 3:
            orientacoes = [f['orientacao'] for f in fotos]
            verticais = sum(1 for o in orientacoes if o == 'retrato')
            horizontais = sum(1 for o in orientacoes if o in ['paisagem', 'quadrada'])
            
            if verticais == 1 and horizontais == 2:
                return 'L3C'
            elif horizontais == 3:
                return 'L3D'
            else:
                return 'L3A'
        
        elif num_fotos == 4:
            return 'L4'
        
        return 'L1'
    
    def atualizar_foto(self, caminho: str, pan_x: float = None, pan_y: float = None, 
                       zoom: float = None, slot_tipo: str = None):
        """Atualiza os ajustes de uma foto específica."""
        for pagina in self.paginas:
            for foto in pagina.fotos:
                if foto.caminho == caminho:
                    if pan_x is not None:
                        foto.pan_x = pan_x
                    if pan_y is not None:
                        foto.pan_y = pan_y
                    if zoom is not None:
                        foto.zoom = zoom
                    if slot_tipo is not None:
                        foto.slot_tipo = slot_tipo
                    return True
        return False
    
    def atualizar_layout_pagina(self, indice_pagina: int, layout: str):
        """Atualiza o layout de uma página específica."""
        if 0 <= indice_pagina < len(self.paginas):
            self.paginas[indice_pagina].layout = layout
            return True
        return False
    
    def reorganizar_pagina(self, indice_pagina: int, novo_layout: str, novas_fotos: List[Dict]):
        """Reorganiza uma página com novo layout e fotos."""
        if 0 <= indice_pagina < len(self.paginas):
            pagina = self.paginas[indice_pagina]
            pagina.layout = novo_layout
            
            # Atualizar fotos
            pagina.fotos = []
            for i, foto_data in enumerate(novas_fotos):
                pagina.fotos.append(FotoSchema(
                    caminho=foto_data['caminho'],
                    largura=foto_data.get('largura', 1920),
                    altura=foto_data.get('altura', 1080),
                    orientacao=foto_data.get('orientacao', 'paisagem'),
                    slot_index=i,
                    pan_x=foto_data.get('pan_x', 0.5),
                    pan_y=foto_data.get('pan_y', 0.5),
                    zoom=foto_data.get('zoom', 1.0),
                    slot_tipo=foto_data.get('slot_tipo', 'auto')
                ))
            return True
        return False
    
    def obter_pagina(self, indice: int) -> Optional[PaginaSchema]:
        """Obtém uma página pelo índice."""
        if 0 <= indice < len(self.paginas):
            return self.paginas[indice]
        return None
    
    def total_paginas(self) -> int:
        """Retorna o total de páginas."""
        return len(self.paginas)
    
    def encontrar_limites_capitulo(self, indice_pagina: int) -> tuple:
        """
        Encontra os limites do capítulo que contém a página especificada.
        Um capítulo é delimitado por subcapas ou capa/contra_capa.
        Retorna (inicio, fim) onde:
        - inicio: índice da primeira página de conteúdo do capítulo
        - fim: índice da última página de conteúdo do capítulo (exclusivo)
        """
        if indice_pagina < 0 or indice_pagina >= len(self.paginas):
            return (None, None)
        
        pagina = self.paginas[indice_pagina]
        if pagina.tipo != 'conteudo':
            return (None, None)
        
        # Buscar início do capítulo (primeira página após subcapa/capa)
        inicio = indice_pagina
        while inicio > 0:
            pag_anterior = self.paginas[inicio - 1]
            if pag_anterior.tipo in ('subcapa', 'capa'):
                break
            if pag_anterior.tipo == 'conteudo':
                inicio -= 1
            else:
                break
        
        # Buscar fim do capítulo (próxima subcapa/contra_capa ou fim)
        fim = indice_pagina + 1
        while fim < len(self.paginas):
            pag = self.paginas[fim]
            if pag.tipo in ('subcapa', 'contra_capa', 'capa'):
                break
            fim += 1
        
        return (inicio, fim)
    
    def redistribuir_fotos_capitulo(self, indice_pagina: int, novo_layout: str,
                                    num_fotos_necessarias: int,
                                    inicio_capitulo: int, fim_capitulo: int) -> bool:
        """
        Redistribui as fotos no capítulo após mudança de layout.
        - Não altera páginas anteriores à página modificada
        - Fotos excedentes vão para o final do capítulo
        """
        if indice_pagina < inicio_capitulo or indice_pagina >= fim_capitulo:
            return False
        
        pagina_atual = self.paginas[indice_pagina]
        if pagina_atual.tipo != 'conteudo':
            return False
        
        # Coletar todas as fotos do capítulo a partir da página atual
        fotos_disponiveis = []
        for i in range(indice_pagina, fim_capitulo):
            if self.paginas[i].tipo == 'conteudo':
                fotos_disponiveis.extend(self.paginas[i].fotos)
        
        if not fotos_disponiveis:
            return False
        
        # Atualizar a página atual com o novo layout
        pagina_atual.layout = novo_layout
        
        # Pegar as fotos necessárias para a página atual
        fotos_para_pagina = fotos_disponiveis[:num_fotos_necessarias]
        fotos_restantes = fotos_disponiveis[num_fotos_necessarias:]
        
        # Atualizar fotos da página atual
        pagina_atual.fotos = []
        for i, foto in enumerate(fotos_para_pagina):
            foto.slot_index = i
            pagina_atual.fotos.append(foto)
        
        # Remover páginas de conteúdo subsequentes no capítulo (serão recriadas)
        paginas_a_remover = []
        for i in range(indice_pagina + 1, fim_capitulo):
            if self.paginas[i].tipo == 'conteudo':
                paginas_a_remover.append(i)
        
        # Remover de trás para frente para não bagunçar índices
        for i in reversed(paginas_a_remover):
            del self.paginas[i]
        
        # Recalcular fim do capítulo após remoção
        novo_fim = indice_pagina + 1
        while novo_fim < len(self.paginas):
            if self.paginas[novo_fim].tipo in ('subcapa', 'contra_capa', 'capa'):
                break
            novo_fim += 1
        
        # Criar novas páginas para as fotos restantes
        posicao_insercao = indice_pagina + 1
        while fotos_restantes:
            # Determinar quantas fotos por página (default: L4 = 4 fotos)
            num_fotos_pagina = min(4, len(fotos_restantes))
            
            # Escolher layout baseado no número de fotos
            if num_fotos_pagina == 1:
                layout = 'L1'
            elif num_fotos_pagina == 2:
                layout = 'L2H'
            elif num_fotos_pagina == 3:
                layout = 'L3D'
            else:
                layout = 'L4'
            
            fotos_nova_pagina = fotos_restantes[:num_fotos_pagina]
            fotos_restantes = fotos_restantes[num_fotos_pagina:]
            
            nova_pagina = PaginaSchema(
                tipo='conteudo',
                layout=layout,
                fotos=[],
                titulo='',
                subtitulo='',
                ano='',
                imagem=''
            )
            
            for i, foto in enumerate(fotos_nova_pagina):
                foto.slot_index = i
                nova_pagina.fotos.append(foto)
            
            self.paginas.insert(posicao_insercao, nova_pagina)
            posicao_insercao += 1
        
        return True
    
    def to_dict(self) -> Dict:
        """Converte o schema para dicionário (para API)."""
        # Contar total de fotos
        total_fotos = sum(len(pag.fotos) for pag in self.paginas)
        
        return {
            'total_fotos': total_fotos,
            'total_paginas': len(self.paginas),
            'paginas': [
                {
                    'tipo': pag.tipo,
                    'layout': pag.layout,
                    'fotos': [asdict(f) for f in pag.fotos],
                    'titulo': pag.titulo,
                    'subtitulo': pag.subtitulo,
                    'ano': pag.ano,
                    'imagem': pag.imagem
                }
                for pag in self.paginas
            ]
        }
    
    def migrar_ajustes_antigos(self):
        """Migra ajustes do formato antigo (ajustes_fotos.json) para o schema."""
        ajustes_path = self.pasta_raiz / "ajustes_fotos.json"
        if not ajustes_path.exists():
            return {}
        
        try:
            with open(ajustes_path, 'r') as f:
                ajustes_antigos = json.load(f)
            
            ajustes = ajustes_antigos.get('ajustes', {})
            
            # Aplicar ajustes às fotos no schema
            for pagina in self.paginas:
                for foto in pagina.fotos:
                    if foto.caminho in ajustes:
                        aj = ajustes[foto.caminho]
                        foto.pan_x = aj.get('pan_x', 0.5)
                        foto.pan_y = aj.get('pan_y', 0.5)
                        foto.zoom = aj.get('zoom', 1.0)
                        foto.slot_tipo = aj.get('slot_tipo', 'auto')
            
            self.salvar()
            print(f"Migrados {len(ajustes)} ajustes do formato antigo")
            return ajustes
        except Exception as e:
            print(f"Erro ao migrar ajustes: {e}")
            return {}
    
    def _carregar_ajustes_antigos(self) -> Dict:
        """Carrega ajustes antigos sem aplicar."""
        ajustes_path = self.pasta_raiz / "ajustes_fotos.json"
        if not ajustes_path.exists():
            return {}
        
        try:
            with open(ajustes_path, 'r') as f:
                ajustes_antigos = json.load(f)
            return ajustes_antigos.get('ajustes', {})
        except:
            return {}


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python schema_manager.py <pasta_raiz> [--regenerar]")
        sys.exit(1)
    
    pasta = Path(sys.argv[1])
    regenerar = '--regenerar' in sys.argv
    
    manager = SchemaManager(pasta)
    
    if regenerar or not manager.carregar():
        print("Gerando schema inicial...")
        manager.gerar_schema_inicial()
        manager.migrar_ajustes_antigos()
        print(f"Schema gerado com {manager.total_paginas()} páginas")
    else:
        print(f"Schema carregado com {manager.total_paginas()} páginas")

