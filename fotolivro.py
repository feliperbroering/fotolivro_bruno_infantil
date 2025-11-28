#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Geração de Fotolivro em PDF

Este script gera um fotolivro em PDF (formato A4 paisagem) a partir de fotos
organizadas em 5 pastas, cada uma representando um ano do Infantil.

RECURSOS:
- Detecção automática de rostos para enquadramento inteligente
- Crop otimizado que preserva rostos e evita cortar pessoas
- Layouts automáticos para 1, 2 ou 3 fotos por página

PREPARAÇÃO:
- Organize as fotos em 5 pastas: Infantil1, Infantil2, Infantil3, Infantil4, Infantil5
- Cada pasta deve conter as fotos do respectivo ano
- Formatos aceitos: .jpg, .jpeg, .png, .tif, .tiff, .webp

EXECUÇÃO:
    python fotolivro.py <pasta_raiz> <arquivo_saida.pdf>

Exemplo:
    python fotolivro.py ./fotos_bruno ./fotolivro_bruno.pdf

INSTALAÇÃO DAS DEPENDÊNCIAS:
    pip install reportlab pillow opencv-python
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    import cv2
    import numpy as np
except ImportError as e:
    print(f"ERRO: Biblioteca necessária não instalada: {e}")
    print("\nInstale as dependências com:")
    print("  pip install reportlab pillow opencv-python")
    sys.exit(1)

# Carregar detectores do OpenCV (Haar Cascades)
# Estes modelos já vêm com o OpenCV e não precisam de download
try:
    FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    UPPERBODY_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')
    FULLBODY_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_fullbody.xml')
    DETECTION_ENABLED = True
except Exception:
    FACE_CASCADE = None
    UPPERBODY_CASCADE = None
    FULLBODY_CASCADE = None
    DETECTION_ENABLED = False
    print("AVISO: Detectores não disponíveis. Usando crop centralizado.")


# ============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ============================================================================

# Ordem fixa das pastas dos anos (sequência obrigatória)
PASTAS_ANOS = ["Infantil1", "Infantil2", "Infantil3", "Infantil4", "Infantil5"]

# Formatos de imagem aceitos
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

# Dimensões A4 em paisagem (297mm x 210mm)
A4_LARGURA_MM = 297
A4_ALTURA_MM = 210

# Margens (em milímetros)
MARGEM_EXTERNA_MM = 10  # Margem de 1 cm em todos os lados externos
MARGEM_LOMBADA_MM = 15  # Margem de 1.5 cm no lado da lombada
ESPACO_ENTRE_FOTOS_MM = 5  # Espaço de 0.5 cm entre fotos vizinhas

# Limites para classificação de proporção
RATIO_QUADRADO_MIN = 0.9
RATIO_QUADRADO_MAX = 1.1

# Informações do fotolivro
TITULO_CAPA = "Bruno Sereia Broering"
SUBTITULO_CAPA = "Momentos no Infantil 1 ao 5"
PERIODO_CAPA = "2021 ~ 2025"

# Títulos das subcapas por ano
TITULOS_ANOS = {
    "Infantil1": ("Infantil 1", "2021"),
    "Infantil2": ("Infantil 2", "2022"),
    "Infantil3": ("Infantil 3", "2023"),
    "Infantil4": ("Infantil 4", "2024"),
    "Infantil5": ("Infantil 5", "2025"),
}

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def mm_to_points(mm_value: float) -> float:
    """Converte milímetros para points (72 points = 1 inch = 25.4mm)."""
    return mm_value * 72.0 / 25.4


def classificar_imagem(largura: int, altura: int) -> str:
    """
    Classifica uma imagem como paisagem, retrato ou quase quadrada.
    
    Retorna:
        'paisagem': largura > altura
        'retrato': altura > largura
        'quadrada': proporção próxima de 1:1 (entre 0.9 e 1.1)
    """
    if largura == 0 or altura == 0:
        return 'paisagem'  # fallback
    
    ratio = largura / altura
    
    if RATIO_QUADRADO_MIN <= ratio <= RATIO_QUADRADO_MAX:
        return 'quadrada'
    elif ratio > 1:
        return 'paisagem'
    else:
        return 'retrato'


def encontrar_pasta_ano(diretorio_raiz: Path, nome_pasta: str) -> Optional[Path]:
    """
    Encontra uma pasta de ano no diretório raiz (case-insensitive).
    
    Retorna o Path da pasta encontrada ou None se não existir.
    """
    diretorio_raiz = Path(diretorio_raiz)
    if not diretorio_raiz.exists():
        return None
    
    # Busca case-insensitive
    for item in diretorio_raiz.iterdir():
        if item.is_dir() and item.name.lower() == nome_pasta.lower():
            return item
    
    return None


def listar_imagens(pasta: Path) -> List[Path]:
    """
    Lista todas as imagens válidas em uma pasta, ordenadas por nome.
    
    Retorna lista de Paths das imagens encontradas.
    """
    imagens = []
    if not pasta.exists() or not pasta.is_dir():
        return imagens
    
    for arquivo in sorted(pasta.iterdir()):
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_IMAGEM:
            imagens.append(arquivo)
    
    return imagens


def obter_dimensoes_imagem(caminho: Path) -> Tuple[int, int]:
    """
    Obtém largura e altura de uma imagem em pixels.
    
    Retorna (largura, altura).
    """
    try:
        with Image.open(caminho) as img:
            return img.size  # (largura, altura)
    except Exception as e:
        print(f"AVISO: Não foi possível ler dimensões de {caminho}: {e}")
        return (1000, 1000)  # fallback


# ============================================================================
# DETECÇÃO DE PESSOAS E CROP INTELIGENTE
# ============================================================================

def detectar_pessoas(caminho: Path) -> Tuple[List[Tuple[int, int, int, int]], int]:
    """
    Detecta pessoas em uma imagem usando OpenCV Haar Cascades.
    Combina detecção de rostos, corpo superior e corpo inteiro.
    
    Args:
        caminho: Caminho da imagem
    
    Retorna:
        Tupla com:
        - Lista de bounding boxes (x, y, largura, altura) das pessoas detectadas
        - Número de rostos detectados (para decidir layout)
    """
    if not DETECTION_ENABLED:
        return [], 0
    
    try:
        # Carregar imagem com OpenCV
        img = cv2.imread(str(caminho))
        if img is None:
            return [], 0
        
        # Converter para escala de cinza (necessário para Haar Cascade)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        regioes = []
        num_rostos = 0
        
        # 1. Detectar rostos (mais preciso)
        if FACE_CASCADE is not None:
            faces = FACE_CASCADE.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for (x, y, w, h) in faces:
                # Expandir a região do rosto para incluir corpo estimado
                # Rosto normalmente é ~1/7 da altura da pessoa
                corpo_h = h * 5  # Estimar altura do corpo
                corpo_y = y  # Manter topo no rosto (não subir)
                corpo_w = int(w * 2)  # Corpo é mais largo que rosto
                corpo_x = x - int(w * 0.5)  # Centralizar
                
                # Garantir que está dentro da imagem
                corpo_x = max(0, corpo_x)
                corpo_y = max(0, corpo_y)
                corpo_w = min(img.shape[1] - corpo_x, corpo_w)
                corpo_h = min(img.shape[0] - corpo_y, corpo_h)
                
                regioes.append((corpo_x, corpo_y, corpo_w, corpo_h))
                num_rostos += 1
        
        # 2. Detectar corpo superior (se não encontrou rostos suficientes)
        if len(regioes) < 2 and UPPERBODY_CASCADE is not None:
            upperbodies = UPPERBODY_CASCADE.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(50, 50),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for (x, y, w, h) in upperbodies:
                # Verificar se não sobrepõe muito com regiões existentes
                sobrepoe = False
                for (rx, ry, rw, rh) in regioes:
                    # Calcular interseção
                    ix = max(x, rx)
                    iy = max(y, ry)
                    ix2 = min(x + w, rx + rw)
                    iy2 = min(y + h, ry + rh)
                    if ix < ix2 and iy < iy2:
                        sobrepoe = True
                        break
                
                if not sobrepoe:
                    # Expandir para baixo (incluir pernas)
                    corpo_h = int(h * 2)
                    corpo_h = min(img.shape[0] - y, corpo_h)
                    regioes.append((int(x), int(y), int(w), corpo_h))
        
        # 3. Detectar corpo inteiro (fallback)
        if len(regioes) < 1 and FULLBODY_CASCADE is not None:
            fullbodies = FULLBODY_CASCADE.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(50, 100),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for (x, y, w, h) in fullbodies:
                regioes.append((int(x), int(y), int(w), int(h)))
        
        return regioes, num_rostos
    
    except Exception:
        # Falha silenciosa - usar fallback
        return [], 0


def detectar_rostos(caminho: Path) -> List[Tuple[int, int, int, int]]:
    """
    Wrapper para compatibilidade - retorna apenas as regiões de pessoas.
    """
    regioes, _ = detectar_pessoas(caminho)
    return regioes


def calcular_regiao_rostos(rostos: List[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    """
    Calcula a união (bounding box) de todos os rostos detectados.
    
    Args:
        rostos: Lista de bounding boxes dos rostos
    
    Retorna:
        Bounding box (x, y, largura, altura) que engloba todos os rostos,
        ou None se a lista estiver vazia.
    """
    if not rostos:
        return None
    
    # Encontrar os limites extremos
    x_min = min(r[0] for r in rostos)
    y_min = min(r[1] for r in rostos)
    x_max = max(r[0] + r[2] for r in rostos)
    y_max = max(r[1] + r[3] for r in rostos)
    
    return (x_min, y_min, x_max - x_min, y_max - y_min)


def calcular_crop_inteligente(
    img_largura: int,
    img_altura: int,
    slot_largura: float,
    slot_altura: float,
    rostos: List[Tuple[int, int, int, int]]
) -> Tuple[int, int, int, int]:
    """
    Calcula o melhor crop da imagem que PRESERVA os rostos (não corta-os).
    
    Estratégia:
    1. Começar com o MAIOR crop possível que caiba no aspect ratio do slot
    2. Se há rostos, ajustar a posição do crop para evitar cortá-los
    3. Preferir cortar fundo (bordas sem rostos) em vez de rostos
    
    Args:
        img_largura: Largura da imagem em pixels
        img_altura: Altura da imagem em pixels
        slot_largura: Largura do slot em points
        slot_altura: Altura do slot em points
        rostos: Lista de bounding boxes dos rostos
    
    Retorna:
        (x, y, largura, altura) do crop na imagem original em pixels.
    """
    ratio_slot = slot_largura / slot_altura
    ratio_img = img_largura / img_altura if img_altura > 0 else 1.0
    
    # Calcular o maior crop possível com o aspect ratio do slot
    if ratio_img >= ratio_slot:
        # Imagem mais larga que o slot: usar altura total, cortar largura
        crop_h = img_altura
        crop_w = int(img_altura * ratio_slot)
    else:
        # Imagem mais alta que o slot: usar largura total, cortar altura
        crop_w = img_largura
        crop_h = int(img_largura / ratio_slot)
    
    # Se não há rostos, usar crop centralizado
    if not rostos:
        crop_x = (img_largura - crop_w) // 2
        crop_y = (img_altura - crop_h) // 2
        return (crop_x, crop_y, crop_w, crop_h)
    
    # Calcular o centro dos rostos (ponderado)
    total_area = 0
    centro_x = 0
    centro_y = 0
    
    for (rx, ry, rw, rh) in rostos:
        area = rw * rh
        total_area += area
        centro_x += (rx + rw / 2) * area
        centro_y += (ry + rh / 2) * area
    
    if total_area > 0:
        centro_x = centro_x / total_area
        centro_y = centro_y / total_area
    else:
        centro_x = img_largura / 2
        centro_y = img_altura / 2
    
    # Calcular a região que contém todos os rostos (com margem)
    regiao_rostos = calcular_regiao_rostos(rostos)
    if regiao_rostos:
        face_x, face_y, face_w, face_h = regiao_rostos
        # Adicionar margem de 10% ao redor dos rostos
        margem = 0.1
        face_x = max(0, face_x - int(face_w * margem))
        face_y = max(0, face_y - int(face_h * margem))
        face_w = min(img_largura - face_x, int(face_w * (1 + 2 * margem)))
        face_h = min(img_altura - face_y, int(face_h * (1 + 2 * margem)))
    else:
        face_x, face_y, face_w, face_h = 0, 0, img_largura, img_altura
    
    # Posicionar o crop tentando manter os rostos dentro
    # Começar centralizando no centro dos rostos
    crop_x = int(centro_x - crop_w / 2)
    crop_y = int(centro_y - crop_h / 2)
    
    # Ajustar para garantir que os rostos fiquem dentro do crop
    # Se os rostos estão mais à esquerda que o crop, mover crop para esquerda
    if face_x < crop_x:
        crop_x = max(0, face_x)
    # Se os rostos estão mais à direita que o crop
    if face_x + face_w > crop_x + crop_w:
        crop_x = min(img_largura - crop_w, face_x + face_w - crop_w)
    
    # Se os rostos estão mais acima que o crop
    if face_y < crop_y:
        crop_y = max(0, face_y)
    # Se os rostos estão mais abaixo que o crop
    if face_y + face_h > crop_y + crop_h:
        crop_y = min(img_altura - crop_h, face_y + face_h - crop_h)
    
    # Clamping final para garantir que está dentro da imagem
    crop_x = max(0, min(crop_x, img_largura - crop_w))
    crop_y = max(0, min(crop_y, img_altura - crop_h))
    
    # Garantir dimensões válidas
    crop_w = max(1, min(crop_w, img_largura - crop_x))
    crop_h = max(1, min(crop_h, img_altura - crop_y))
    
    return (crop_x, crop_y, crop_w, crop_h)


def _crop_centralizado(img_largura: int, img_altura: int, ratio_slot: float) -> Tuple[int, int, int, int]:
    """
    Calcula um crop centralizado com o aspect ratio do slot.
    
    Fallback quando não há rostos detectados.
    """
    ratio_img = img_largura / img_altura if img_altura > 0 else 1.0
    
    if ratio_img >= ratio_slot:
        # Imagem mais larga: cortar nas laterais
        nova_largura = int(img_altura * ratio_slot)
        x = (img_largura - nova_largura) // 2
        return (x, 0, nova_largura, img_altura)
    else:
        # Imagem mais alta: cortar em cima/baixo
        nova_altura = int(img_largura / ratio_slot)
        y = (img_altura - nova_altura) // 2
        return (0, y, img_largura, nova_altura)


# ============================================================================
# CLASSES E ESTRUTURAS DE DADOS
# ============================================================================

class Layout(Enum):
    """Tipos de layout disponíveis para as páginas."""
    L1 = "1 foto"           # 1 foto ocupando toda área útil
    L2H = "2 fotos horizontal"  # 2 fotos lado a lado
    L2V = "2 fotos vertical"     # 2 fotos empilhadas
    L3A = "3 fotos (2+1)"    # 2 em cima, 1 embaixo
    L3B = "3 fotos (1+2)"    # 1 em cima, 2 embaixo
    L3C = "3 fotos (1v+2h)"  # 1 vertical à direita, 2 horizontais à esquerda
    L3D = "3 fotos (1h+2h)"  # 1 horizontal grande em cima, 2 horizontais menores embaixo
    L4 = "4 fotos (2x2)"     # Grid 2x2 para fotos com poucos elementos


class FotoInfo:
    """Informações sobre uma foto, incluindo pessoas detectadas."""
    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.largura, self.altura = obter_dimensoes_imagem(caminho)
        self.orientacao = classificar_imagem(self.largura, self.altura)
        self.ratio = self.largura / self.altura if self.altura > 0 else 1.0
        
        # Detectar pessoas na foto (para crop inteligente e decisão de layout)
        self.rostos, self.num_rostos = detectar_pessoas(caminho)
        
        # Classificar como "simples" se tem poucos rostos (bom para layout 4x4)
        self.simples = self.num_rostos <= 2


class GeradorFotolivro:
    """Classe principal para gerar o fotolivro em PDF."""
    
    def __init__(self, pasta_raiz: Path, arquivo_saida: Path):
        self.pasta_raiz = Path(pasta_raiz)
        self.arquivo_saida = Path(arquivo_saida)
        
        # Dimensões da página em points
        self.largura_pagina = mm_to_points(A4_LARGURA_MM)
        self.altura_pagina = mm_to_points(A4_ALTURA_MM)
        
        # Margens em points
        self.margem_externa = mm_to_points(MARGEM_EXTERNA_MM)  # 1 cm
        self.margem_lombada = mm_to_points(MARGEM_LOMBADA_MM)  # 2 cm
        self.espaco_entre_fotos = mm_to_points(ESPACO_ENTRE_FOTOS_MM)  # 1 cm
        
        # Canvas do PDF
        self.canvas = None
        self.numero_pagina = 0
        
        # Ajustes de pan/zoom definidos pelo usuário (carregado do JSON)
        self.ajustes_usuario = {}
        
    def validar_estrutura(self) -> bool:
        """
        Valida se a estrutura de pastas está correta.
        
        Retorna True se tudo estiver OK, False caso contrário.
        """
        if not self.pasta_raiz.exists():
            print(f"ERRO: Pasta raiz não encontrada: {self.pasta_raiz}")
            return False
        
        if not self.pasta_raiz.is_dir():
            print(f"ERRO: O caminho não é um diretório: {self.pasta_raiz}")
            return False
        
        # Verificar se todas as pastas dos anos existem
        pastas_faltando = []
        for nome_pasta in PASTAS_ANOS:
            pasta_encontrada = encontrar_pasta_ano(self.pasta_raiz, nome_pasta)
            if pasta_encontrada is None:
                pastas_faltando.append(nome_pasta)
        
        if pastas_faltando:
            print(f"ERRO: Pastas não encontradas dentro de {self.pasta_raiz}:")
            for pasta in pastas_faltando:
                print(f"  - {pasta}")
            return False
        
        # Verificar se há imagens em cada pasta
        for nome_pasta in PASTAS_ANOS:
            pasta = encontrar_pasta_ano(self.pasta_raiz, nome_pasta)
            imagens = listar_imagens(pasta)
            if not imagens:
                print(f"AVISO: Nenhuma imagem válida encontrada na pasta {nome_pasta}.")
        
        return True
    
    def calcular_crop_com_ajuste(
        self,
        img_largura: int,
        img_altura: int,
        slot_largura: float,
        slot_altura: float,
        ajuste: dict
    ) -> Tuple[int, int, int, int]:
        """
        Calcula o crop baseado nos ajustes do usuário (pan_x, pan_y, zoom).
        
        Args:
            img_largura: Largura da imagem em pixels
            img_altura: Altura da imagem em pixels
            slot_largura: Largura do slot em points
            slot_altura: Altura do slot em points
            ajuste: Dicionário com pan_x, pan_y (0-1) e zoom (1+)
        
        Retorna:
            Tupla (x, y, largura, altura) do crop em pixels
        """
        pan_x = ajuste.get('pan_x', 0.5)
        pan_y = ajuste.get('pan_y', 0.5)
        zoom = ajuste.get('zoom', 1.0)
        
        # Calcular aspect ratio do slot
        ratio_slot = slot_largura / slot_altura
        ratio_img = img_largura / img_altura
        
        # Calcular dimensões do crop base (modo cover)
        if ratio_img > ratio_slot:
            # Imagem mais larga que o slot: limitar pela altura
            crop_h = img_altura
            crop_w = int(crop_h * ratio_slot)
        else:
            # Imagem mais alta que o slot: limitar pela largura
            crop_w = img_largura
            crop_h = int(crop_w / ratio_slot)
        
        # Aplicar zoom (reduz o tamanho do crop)
        crop_w = int(crop_w / zoom)
        crop_h = int(crop_h / zoom)
        
        # Garantir que o crop não seja maior que a imagem
        crop_w = min(crop_w, img_largura)
        crop_h = min(crop_h, img_altura)
        
        # Calcular posição baseada no pan (0=esquerda/topo, 1=direita/baixo)
        max_x = img_largura - crop_w
        max_y = img_altura - crop_h
        
        crop_x = int(pan_x * max_x)
        crop_y = int(pan_y * max_y)
        
        # Garantir bounds
        crop_x = max(0, min(crop_x, max_x))
        crop_y = max(0, min(crop_y, max_y))
        
        return (crop_x, crop_y, crop_w, crop_h)
    
    def calcular_area_util(self, pagina_impar: bool) -> Tuple[float, float, float, float]:
        """
        Calcula a área útil da página (sem margens).
        
        Grade de margens:
        - 1 cm em todos os lados externos
        - 2 cm no lado da lombada (esquerda em ímpares, direita em pares)
        
        Args:
            pagina_impar: True se página ímpar (lombada à esquerda), False se par (lombada à direita)
        
        Retorna:
            (x, y, largura, altura) da área útil em points
        """
        # Página ímpar: lombada à ESQUERDA (margem esquerda = 2cm, direita = 1cm)
        # Página par: lombada à DIREITA (margem esquerda = 1cm, direita = 2cm)
        if pagina_impar:
            margem_esquerda = self.margem_lombada  # 2 cm (lombada)
            margem_direita = self.margem_externa   # 1 cm
        else:
            margem_esquerda = self.margem_externa  # 1 cm
            margem_direita = self.margem_lombada   # 2 cm (lombada)
        
        # Margens superior e inferior: 1 cm
        margem_superior = self.margem_externa
        margem_inferior = self.margem_externa
        
        # Área útil
        x = margem_esquerda
        y = margem_inferior
        largura = self.largura_pagina - margem_esquerda - margem_direita
        altura = self.altura_pagina - margem_superior - margem_inferior
        
        return (x, y, largura, altura)
    
    def calcular_layout_l1(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L1 (1 foto).
        
        Retorna lista com uma tupla (x, y, largura, altura) da área da foto.
        """
        x, y, largura, altura = area_util
        return [(x, y, largura, altura)]
    
    def calcular_layout_l2h(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L2H (2 fotos lado a lado).
        
        Retorna lista com duas tuplas (x, y, largura, altura) das áreas das fotos.
        """
        x, y, largura, altura = area_util
        
        # Dividir largura em 2, com espaço entre
        largura_foto = (largura - self.espaco_entre_fotos) / 2
        
        foto1 = (x, y, largura_foto, altura)
        foto2 = (x + largura_foto + self.espaco_entre_fotos, y, largura_foto, altura)
        
        return [foto1, foto2]
    
    def calcular_layout_l2v(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L2V (2 fotos empilhadas).
        
        Retorna lista com duas tuplas (x, y, largura, altura) das áreas das fotos.
        """
        x, y, largura, altura = area_util
        
        # Dividir altura em 2, com espaço entre
        altura_foto = (altura - self.espaco_entre_fotos) / 2
        
        foto1 = (x, y + altura_foto + self.espaco_entre_fotos, largura, altura_foto)
        foto2 = (x, y, largura, altura_foto)
        
        return [foto1, foto2]
    
    def calcular_layout_l3a(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L3A (2 em cima, 1 embaixo).
        
        Grade: toda área útil é ocupada por 3 slots com 1 cm entre eles.
        - Linha superior: 2 fotos lado a lado (50% altura cada, dividem largura)
        - Linha inferior: 1 foto ocupando toda largura (50% altura)
        
        Retorna lista com três tuplas (x, y, largura, altura) das áreas das fotos.
        """
        x, y, largura, altura = area_util
        
        # Dividir altura em 2 linhas com espaço entre
        altura_linha = (altura - self.espaco_entre_fotos) / 2
        
        # Fotos superiores: dividem a largura com espaço entre
        largura_foto_superior = (largura - self.espaco_entre_fotos) / 2
        
        foto1 = (x, y + altura_linha + self.espaco_entre_fotos, largura_foto_superior, altura_linha)
        foto2 = (x + largura_foto_superior + self.espaco_entre_fotos, y + altura_linha + self.espaco_entre_fotos, 
                 largura_foto_superior, altura_linha)
        
        # Foto inferior: ocupa toda a largura
        foto3 = (x, y, largura, altura_linha)
        
        return [foto1, foto2, foto3]
    
    def calcular_layout_l3b(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L3B (1 em cima, 2 embaixo).
        
        Grade: toda área útil é ocupada por 3 slots com 1 cm entre eles.
        - Linha superior: 1 foto ocupando toda largura (50% altura)
        - Linha inferior: 2 fotos lado a lado (50% altura cada, dividem largura)
        
        Retorna lista com três tuplas (x, y, largura, altura) das áreas das fotos.
        """
        x, y, largura, altura = area_util
        
        # Dividir altura em 2 linhas com espaço entre
        altura_linha = (altura - self.espaco_entre_fotos) / 2
        
        # Foto superior: ocupa toda a largura
        foto1 = (x, y + altura_linha + self.espaco_entre_fotos, largura, altura_linha)
        
        # Fotos inferiores: dividem a largura com espaço entre
        largura_foto_inferior = (largura - self.espaco_entre_fotos) / 2
        foto2 = (x, y, largura_foto_inferior, altura_linha)
        foto3 = (x + largura_foto_inferior + self.espaco_entre_fotos, y, largura_foto_inferior, altura_linha)
        
        return [foto1, foto2, foto3]
    
    def calcular_layout_l3c(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L3C (1 vertical à direita, 2 horizontais à esquerda).
        
        Grade: toda área útil é ocupada por 3 slots com 1 cm entre eles.
        - Coluna esquerda (60%): 2 fotos horizontais empilhadas (dividem altura)
        - Coluna direita (40%): 1 foto vertical ocupando toda altura
        
        Retorna lista com três tuplas (x, y, largura, altura) das áreas das fotos.
        Ordem: [vertical, horizontal_superior, horizontal_inferior]
        """
        x, y, largura, altura = area_util
        
        # Dividir largura em 2 colunas (60% esquerda, 40% direita) com espaço entre
        largura_esquerda = (largura - self.espaco_entre_fotos) * 0.60
        largura_direita = (largura - self.espaco_entre_fotos) * 0.40
        
        # Área esquerda: 2 fotos horizontais dividindo verticalmente
        altura_horizontal = (altura - self.espaco_entre_fotos) / 2
        
        # Foto horizontal superior (esquerda)
        foto_h1 = (x, y + altura_horizontal + self.espaco_entre_fotos, largura_esquerda, altura_horizontal)
        
        # Foto horizontal inferior (esquerda)
        foto_h2 = (x, y, largura_esquerda, altura_horizontal)
        
        # Foto vertical (direita) - ocupa toda altura
        x_vertical = x + largura_esquerda + self.espaco_entre_fotos
        foto_v = (x_vertical, y, largura_direita, altura)
        
        # Retornar na ordem: [vertical, horizontal_superior, horizontal_inferior]
        return [foto_v, foto_h1, foto_h2]
    
    def calcular_layout_l3d(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L3D (1 horizontal em cima, 2 horizontais embaixo).
        
        Grade: toda área útil é ocupada por 3 slots com 1 cm entre eles.
        - Linha superior: 1 foto ocupando toda largura (50% altura)
        - Linha inferior: 2 fotos lado a lado (50% altura cada, dividem largura)
        
        Este layout é idêntico ao L3B, usado para 3 fotos horizontais.
        
        Retorna lista com três tuplas (x, y, largura, altura) das áreas das fotos.
        Ordem: [foto_cima, foto_esquerda, foto_direita]
        """
        x, y, largura, altura = area_util
        
        # Dividir altura em 2 linhas com espaço entre
        altura_linha = (altura - self.espaco_entre_fotos) / 2
        
        # Foto superior: ocupa toda a largura
        foto_cima = (x, y + altura_linha + self.espaco_entre_fotos, largura, altura_linha)
        
        # Fotos inferiores: dividem a largura com espaço entre
        largura_foto_inferior = (largura - self.espaco_entre_fotos) / 2
        foto_esquerda = (x, y, largura_foto_inferior, altura_linha)
        foto_direita = (x + largura_foto_inferior + self.espaco_entre_fotos, y, largura_foto_inferior, altura_linha)
        
        # Retornar na ordem: [foto_cima, foto_esquerda, foto_direita]
        return [foto_cima, foto_esquerda, foto_direita]
    
    def calcular_layout_l4(self, area_util: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
        """
        Calcula coordenadas para layout L4 (grid 2x2 de fotos).
        
        Grade: 4 fotos em grid 2x2 com espaço entre elas.
        Ideal para fotos com poucos elementos/pessoas.
        
        Retorna lista com quatro tuplas (x, y, largura, altura) das áreas das fotos.
        Ordem: [topo_esquerda, topo_direita, baixo_esquerda, baixo_direita]
        """
        x, y, largura, altura = area_util
        
        # Dividir em grid 2x2
        largura_foto = (largura - self.espaco_entre_fotos) / 2
        altura_foto = (altura - self.espaco_entre_fotos) / 2
        
        # Linha superior
        foto_topo_esq = (x, y + altura_foto + self.espaco_entre_fotos, largura_foto, altura_foto)
        foto_topo_dir = (x + largura_foto + self.espaco_entre_fotos, y + altura_foto + self.espaco_entre_fotos, 
                         largura_foto, altura_foto)
        
        # Linha inferior
        foto_baixo_esq = (x, y, largura_foto, altura_foto)
        foto_baixo_dir = (x + largura_foto + self.espaco_entre_fotos, y, largura_foto, altura_foto)
        
        return [foto_topo_esq, foto_topo_dir, foto_baixo_esq, foto_baixo_dir]
    
    def redimensionar_foto_contain(self, foto: FotoInfo, box: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """
        Calcula dimensões e posição para redimensionar uma foto em modo "cover" dentro de uma box.
        Usa "cover" para preencher toda a área, garantindo que sempre haja espaço de 1cm entre fotos.
        
        Args:
            foto: Informações da foto
            box: (x, y, largura, altura) da área disponível
        
        Retorna:
            (x, y, largura_redimensionada, altura_redimensionada) para posicionar a foto
        """
        x_box, y_box, largura_box, altura_box = box
        
        # Calcular ratios
        ratio_foto = foto.ratio
        ratio_box = largura_box / altura_box if altura_box > 0 else 1.0
        
        # Modo "cover": preencher toda a área, podendo cortar partes da foto
        # Escolher a dimensão que faz a foto preencher toda a box
        if ratio_foto >= ratio_box:
            # Foto é mais larga: preencher pela altura e cortar nas laterais
            altura_final = altura_box
            largura_final = altura_final * ratio_foto
        else:
            # Foto é mais alta: preencher pela largura e cortar em cima/baixo
            largura_final = largura_box
            altura_final = largura_final / ratio_foto
        
        # Centralizar na box (pode haver corte nas bordas)
        x_final = x_box + (largura_box - largura_final) / 2
        y_final = y_box + (altura_box - altura_final) / 2
        
        return (x_final, y_final, largura_final, altura_final)
    
    def escolher_layout(self, fotos: List[FotoInfo]) -> Tuple[Layout, List[Tuple[float, float, float, float]], List[FotoInfo]]:
        """
        Escolhe o layout apropriado para um grupo de fotos.
        Considera tipos de slot definidos pelo usuário.
        
        Args:
            fotos: Lista de 1, 2, 3 ou 4 fotos
        
        Retorna:
            (Layout, lista de boxes para as fotos, fotos reorganizadas se necessário)
        """
        num_fotos = len(fotos)
        area_util = self.calcular_area_util(self.numero_pagina % 2 == 1)  # True se ímpar
        
        # Obter tipos de slot das fotos
        tipos = [self.obter_slot_tipo(f) for f in fotos]
        
        if num_fotos == 1:
            boxes = self.calcular_layout_l1(area_util)
            return (Layout.L1, boxes, fotos)
        
        elif num_fotos == 2:
            # Verificar tipos de slot definidos
            tipo1, tipo2 = tipos[0], tipos[1]
            
            # Se uma é vertical esquerda e outra direita, usar L2H
            if (tipo1 == 'fv-l' and tipo2 == 'fv-r') or (tipo1 == 'fv-r' and tipo2 == 'fv-l'):
                # Ordenar: esquerda primeiro
                if tipo1 == 'fv-r':
                    fotos = [fotos[1], fotos[0]]
                boxes = self.calcular_layout_l2h(area_util)
                return (Layout.L2H, boxes, fotos)
            
            # Se uma é horizontal topo e outra baixo, usar L2V
            if (tipo1 == 'fh-t' and tipo2 == 'fh-b') or (tipo1 == 'fh-b' and tipo2 == 'fh-t'):
                # Ordenar: topo primeiro
                if tipo1 == 'fh-b':
                    fotos = [fotos[1], fotos[0]]
                boxes = self.calcular_layout_l2v(area_util)
                return (Layout.L2V, boxes, fotos)
            
            # Se qualquer uma é vertical (fv-l ou fv-r), usar L2H
            if tipo1 in ['fv-l', 'fv-r'] or tipo2 in ['fv-l', 'fv-r']:
                # Garantir ordem correta: fv-l à esquerda, fv-r à direita
                if tipo1 == 'fv-r' or tipo2 == 'fv-l':
                    fotos = [fotos[1], fotos[0]]
                boxes = self.calcular_layout_l2h(area_util)
                return (Layout.L2H, boxes, fotos)
            
            # Se qualquer uma é horizontal (fh-t ou fh-b), usar L2V
            if tipo1 in ['fh-t', 'fh-b'] or tipo2 in ['fh-t', 'fh-b']:
                boxes = self.calcular_layout_l2v(area_util)
                return (Layout.L2V, boxes, fotos)
            
            # Padrão: L2H (lado a lado) para 2 fotos
            boxes = self.calcular_layout_l2h(area_util)
            return (Layout.L2H, boxes, fotos)
        
        elif num_fotos == 3:
            # Verificar orientações das fotos
            orientacoes = [f.orientacao for f in fotos]
            
            # Contar verticais e horizontais
            verticais = [i for i, o in enumerate(orientacoes) if o == 'retrato']
            horizontais = [i for i, o in enumerate(orientacoes) if o in ['paisagem', 'quadrada']]
            
            # Se temos exatamente 1 vertical e 2 horizontais, usar L3C
            if len(verticais) == 1 and len(horizontais) == 2:
                foto_vertical = fotos[verticais[0]]
                fotos_horizontais = [fotos[i] for i in horizontais]
                fotos_reorganizadas = [foto_vertical] + fotos_horizontais
                
                boxes = self.calcular_layout_l3c(area_util)
                return (Layout.L3C, boxes, fotos_reorganizadas)
            
            # Se temos 3 fotos horizontais, usar L3D
            if len(horizontais) == 3:
                boxes = self.calcular_layout_l3d(area_util)
                return (Layout.L3D, boxes, fotos)
            
            # Caso contrário, usar layouts tradicionais
            if orientacoes[0] in ['paisagem', 'quadrada'] and orientacoes[1] in ['paisagem', 'quadrada']:
                boxes = self.calcular_layout_l3a(area_util)
                return (Layout.L3A, boxes, fotos)
            else:
                boxes = self.calcular_layout_l3b(area_util)
                return (Layout.L3B, boxes, fotos)
        
        elif num_fotos == 4:
            boxes = self.calcular_layout_l4(area_util)
            return (Layout.L4, boxes, fotos)
        
        else:
            boxes = self.calcular_layout_l1(area_util)
            return (Layout.L1, boxes, fotos)
    
    def obter_slot_tipo(self, foto) -> str:
        """
        Obtém o tipo de slot definido pelo usuário para a foto.
        Retorna 'auto' se não definido.
        """
        if not self.ajustes_usuario:
            return 'auto'
        
        try:
            foto_path = str(foto.caminho.relative_to(self.pasta_raiz))
        except ValueError:
            foto_path = str(foto.caminho)
        
        ajustes = self.ajustes_usuario.get('ajustes', {})
        ajuste = ajustes.get(foto_path, {})
        return ajuste.get('slot_tipo', 'auto')
    
    def agrupar_fotos(self, fotos: List[FotoInfo]) -> List[List[FotoInfo]]:
        """
        Agrupa fotos em páginas considerando tipos de slot definidos pelo usuário.
        
        Tipos de slot:
        - 'full': página inteira (1 foto)
        - 'fv-l', 'fv-r': vertical (metade esquerda/direita)
        - 'fh-t', 'fh-b': horizontal (metade superior/inferior)
        - 'square': slot menor (para layouts 3-4 fotos)
        - 'auto': escolha automática
        
        Retorna lista de grupos, onde cada grupo é uma lista de 1-4 fotos.
        """
        grupos = []
        i = 0
        
        # IMPORTANTE: Quando há ajustes do usuário, usar a mesma lógica do preview
        # No preview, todas as fotos são consideradas "simples" (sem detecção de rostos)
        # Para manter consistência, quando há ajustes, tratamos todas como simples
        usar_modo_preview = bool(self.ajustes_usuario and self.ajustes_usuario.get('ajustes'))
        
        while i < len(fotos):
            foto_atual = fotos[i]
            restantes = len(fotos) - i
            slot_tipo = self.obter_slot_tipo(foto_atual)
            
            # Foto com tipo 'full' vai sozinha
            if slot_tipo == 'full':
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Fotos verticais (fv-l ou fv-r) precisam de complemento
            if slot_tipo in ['fv-l', 'fv-r']:
                # Procurar outra foto vertical ou squares para completar
                if restantes >= 2:
                    proxima = fotos[i + 1]
                    tipo_proxima = self.obter_slot_tipo(proxima)
                    
                    # Se a próxima é vertical do outro lado ou square, formar par
                    if tipo_proxima in ['fv-l', 'fv-r', 'square', 'auto']:
                        grupos.append([foto_atual, proxima])
                        i += 2
                        continue
                
                # Se não encontrou par, coloca sozinha como full
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Fotos horizontais (fh-t ou fh-b) precisam de complemento
            if slot_tipo in ['fh-t', 'fh-b']:
                if restantes >= 2:
                    proxima = fotos[i + 1]
                    tipo_proxima = self.obter_slot_tipo(proxima)
                    
                    if tipo_proxima in ['fh-t', 'fh-b', 'square', 'auto']:
                        grupos.append([foto_atual, proxima])
                        i += 2
                        continue
                
                grupos.append([foto_atual])
                i += 1
                continue
            
            # Lógica padrão para fotos 'auto' e 'square'
            # IMPORTANTE: Verificar se alguma das próximas fotos tem slot_tipo especial
            def encontrar_limite_grupo(inicio, max_fotos):
                """Encontra quantas fotos podem ser agrupadas antes de uma com slot_tipo especial."""
                limite = 0
                for j in range(inicio, min(inicio + max_fotos, len(fotos))):
                    tipo_j = self.obter_slot_tipo(fotos[j])
                    # Parar se a foto tem slot_tipo especial
                    if tipo_j in ['full', 'fv-l', 'fv-r', 'fh-t', 'fh-b']:
                        break
                    limite += 1
                return limite
            
            # Calcular quantas fotos podemos agrupar
            max_grupo = encontrar_limite_grupo(i, 4)
            
            if max_grupo >= 4 and restantes >= 4:
                proximas_4 = fotos[i:i+4]
                # Contar quantas são square ou simples
                # IMPORTANTE: Em modo preview, todas são consideradas simples
                square_count = sum(1 for f in proximas_4 
                                   if self.obter_slot_tipo(f) == 'square' or 
                                      (usar_modo_preview or f.simples))
                
                if square_count >= 3:
                    grupos.append(proximas_4)
                    i += 4
                    continue
            
            if max_grupo >= 3 and restantes >= 3:
                proximas_3 = fotos[i:i+3]
                orientacoes = [f.orientacao for f in proximas_3]
                
                paisagem_count = sum(1 for o in orientacoes if o in ['paisagem', 'quadrada'])
                if paisagem_count >= 2:
                    grupos.append(proximas_3)
                    i += 3
                    continue
            
            if max_grupo >= 2 and restantes >= 2:
                grupos.append(fotos[i:i+2])
                i += 2
            
            elif max_grupo >= 1:
                grupos.append([fotos[i]])
                i += 1
            
            else:
                # Não deveria acontecer, mas por segurança
                grupos.append([fotos[i]])
                i += 1
        
        return grupos
    
    def adicionar_pagina(self, fotos: List[FotoInfo]):
        """
        Adiciona uma página ao PDF com as fotos fornecidas.
        
        Usa ajustes do usuário se disponíveis, ou crop inteligente com
        detecção de rostos para preservar as pessoas nas fotos.
        
        Args:
            fotos: Lista de 1, 2 ou 3 fotos para esta página
        """
        self.numero_pagina += 1
        pagina_impar = (self.numero_pagina % 2 == 1)
        
        # Escolher layout (pode reorganizar as fotos se necessário)
        layout, boxes, fotos_ordenadas = self.escolher_layout(fotos)
        
        # Adicionar cada foto na sua box
        for foto, box in zip(fotos_ordenadas, boxes):
            x_box, y_box, w_box, h_box = box
            
            try:
                # Verificar se há ajuste do usuário para esta foto
                foto_path_rel = str(foto.caminho.relative_to(self.pasta_raiz))
                # Os ajustes estão dentro da chave 'ajustes' no JSON
                ajustes_dict = self.ajustes_usuario.get('ajustes', {}) if isinstance(self.ajustes_usuario, dict) else {}
                ajuste_usuario = ajustes_dict.get(foto_path_rel)
                
                if ajuste_usuario:
                    # Usar ajuste do usuário
                    crop_x, crop_y, crop_w, crop_h = self.calcular_crop_com_ajuste(
                        foto.largura, foto.altura,
                        w_box, h_box,
                        ajuste_usuario
                    )
                else:
                    # Usar crop inteligente automático (preserva rostos)
                    crop_x, crop_y, crop_w, crop_h = calcular_crop_inteligente(
                        foto.largura, foto.altura,
                        w_box, h_box,
                        foto.rostos
                    )
                
                # Abrir imagem e aplicar o crop
                with Image.open(foto.caminho) as img:
                    # Aplicar crop na imagem
                    img_cropped = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                    
                    # Converter para ImageReader do ReportLab
                    from io import BytesIO
                    img_buffer = BytesIO()
                    
                    # Manter formato original ou converter para JPEG
                    if img.format in ['JPEG', 'JPG']:
                        img_cropped.save(img_buffer, format='JPEG', quality=95)
                    else:
                        # Converter para RGB se necessário (para JPEG)
                        if img_cropped.mode in ('RGBA', 'P'):
                            img_cropped = img_cropped.convert('RGB')
                        img_cropped.save(img_buffer, format='JPEG', quality=95)
                    
                    img_buffer.seek(0)
                    
                    # Desenhar a imagem recortada no slot
                    self.canvas.drawImage(
                        ImageReader(img_buffer),
                        x_box, y_box,
                        width=w_box,
                        height=h_box,
                        preserveAspectRatio=False,  # O crop já tem o aspect ratio correto
                        mask='auto'
                    )
                
            except Exception as e:
                print(f"AVISO: Erro ao adicionar foto {foto.caminho.name}: {e}")
        
        # Finalizar página atual
        self.canvas.showPage()
    
    def criar_mosaico(self, fotos: List[FotoInfo], largura: int, altura: int) -> Image.Image:
        """
        Cria um mosaico de miniaturas de todas as fotos.
        
        Args:
            fotos: Lista de fotos para o mosaico
            largura: Largura do mosaico em pixels
            altura: Altura do mosaico em pixels
        
        Retorna:
            Imagem PIL com o mosaico
        """
        if not fotos:
            # Criar imagem branca se não houver fotos
            return Image.new('RGB', (largura, altura), 'white')
        
        # Calcular grid (quantas fotos por linha/coluna)
        num_fotos = len(fotos)
        cols = int(np.ceil(np.sqrt(num_fotos * largura / altura)))
        rows = int(np.ceil(num_fotos / cols))
        
        # Tamanho de cada miniatura
        thumb_w = largura // cols
        thumb_h = altura // rows
        
        # Criar imagem do mosaico
        mosaico = Image.new('RGB', (largura, altura), 'black')
        
        for i, foto in enumerate(fotos):
            if i >= cols * rows:
                break
            
            row = i // cols
            col = i % cols
            
            try:
                with Image.open(foto.caminho) as img:
                    # Redimensionar para caber na célula (modo cover)
                    img_ratio = img.width / img.height
                    cell_ratio = thumb_w / thumb_h
                    
                    if img_ratio > cell_ratio:
                        # Imagem mais larga: ajustar pela altura
                        new_h = thumb_h
                        new_w = int(new_h * img_ratio)
                    else:
                        # Imagem mais alta: ajustar pela largura
                        new_w = thumb_w
                        new_h = int(new_w / img_ratio)
                    
                    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    
                    # Crop central
                    left = (new_w - thumb_w) // 2
                    top = (new_h - thumb_h) // 2
                    img_cropped = img_resized.crop((left, top, left + thumb_w, top + thumb_h))
                    
                    # Converter para RGB se necessário
                    if img_cropped.mode != 'RGB':
                        img_cropped = img_cropped.convert('RGB')
                    
                    # Colar no mosaico
                    x = col * thumb_w
                    y = row * thumb_h
                    mosaico.paste(img_cropped, (x, y))
            except Exception:
                pass
        
        return mosaico
    
    def criar_capa(self, todas_fotos: List[FotoInfo]):
        """
        Cria a página de capa.
        Usa imagem pré-gerada se existir em _capas/capa.jpg
        """
        # Verificar se existe capa pré-gerada
        capa_path = self.pasta_raiz / "_capas" / "capa.jpg"
        
        if capa_path.exists():
            # Usar capa pré-gerada (já tem texto e estilo aplicados)
            self.canvas.drawImage(
                str(capa_path),
                0, 0,
                width=self.largura_pagina,
                height=self.altura_pagina,
                preserveAspectRatio=False
            )
            self.canvas.showPage()
            self.numero_pagina += 1
            return
        
        # Fallback: gerar capa dinamicamente
        from io import BytesIO
        
        # Criar mosaico com resolução alta
        largura_px = int(self.largura_pagina * 4)  # 4x para qualidade
        altura_px = int(self.altura_pagina * 4)
        
        mosaico = self.criar_mosaico(todas_fotos, largura_px, altura_px)
        
        # Converter para escala de cinza
        mosaico_gray = mosaico.convert('L')
        
        # Reduzir contraste/brilho para o texto ficar legível
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(mosaico_gray)
        mosaico_dark = enhancer.enhance(0.4)  # Escurecer
        enhancer = ImageEnhance.Contrast(mosaico_dark)
        mosaico_final = enhancer.enhance(0.7)  # Reduzir contraste
        
        # Converter de volta para RGB
        mosaico_final = mosaico_final.convert('RGB')
        
        # Salvar em buffer
        img_buffer = BytesIO()
        mosaico_final.save(img_buffer, format='JPEG', quality=90)
        img_buffer.seek(0)
        
        # Desenhar mosaico
        self.canvas.drawImage(
            ImageReader(img_buffer),
            0, 0,
            width=self.largura_pagina,
            height=self.altura_pagina
        )
        
        # Adicionar título
        self.canvas.setFillColor('white')
        
        # Título principal
        self.canvas.setFont('Helvetica-Bold', 48)
        titulo = TITULO_CAPA
        titulo_w = self.canvas.stringWidth(titulo, 'Helvetica-Bold', 48)
        self.canvas.drawString(
            (self.largura_pagina - titulo_w) / 2,
            self.altura_pagina * 0.55,
            titulo
        )
        
        # Subtítulo
        self.canvas.setFont('Helvetica', 32)
        subtitulo = SUBTITULO_CAPA
        subtitulo_w = self.canvas.stringWidth(subtitulo, 'Helvetica', 32)
        self.canvas.drawString(
            (self.largura_pagina - subtitulo_w) / 2,
            self.altura_pagina * 0.45,
            subtitulo
        )
        
        # Período
        self.canvas.setFont('Helvetica', 28)
        periodo = PERIODO_CAPA
        periodo_w = self.canvas.stringWidth(periodo, 'Helvetica', 28)
        self.canvas.drawString(
            (self.largura_pagina - periodo_w) / 2,
            self.altura_pagina * 0.35,
            periodo
        )
        
        self.canvas.showPage()
        self.numero_pagina += 1
    
    def criar_subcapa(self, fotos_ano: List[FotoInfo], nome_pasta: str):
        """
        Cria uma subcapa para um ano específico.
        Usa imagem pré-gerada se existir em _capas/subcapa_infantilX.jpg
        """
        # Verificar se existe subcapa pré-gerada
        subcapa_path = self.pasta_raiz / "_capas" / f"subcapa_{nome_pasta.lower()}.jpg"
        
        if subcapa_path.exists():
            # Usar subcapa pré-gerada (já tem texto e estilo aplicados)
            self.canvas.drawImage(
                str(subcapa_path),
                0, 0,
                width=self.largura_pagina,
                height=self.altura_pagina,
                preserveAspectRatio=False
            )
            self.canvas.showPage()
            self.numero_pagina += 1
            return
        
        # Fallback: gerar subcapa dinamicamente
        from io import BytesIO
        
        # Obter título do ano
        if nome_pasta.lower() in [k.lower() for k in TITULOS_ANOS.keys()]:
            for k, v in TITULOS_ANOS.items():
                if k.lower() == nome_pasta.lower():
                    titulo_ano, ano = v
                    break
        else:
            titulo_ano = nome_pasta
            ano = ""
        
        # Criar mosaico com resolução alta
        largura_px = int(self.largura_pagina * 4)
        altura_px = int(self.altura_pagina * 4)
        
        mosaico = self.criar_mosaico(fotos_ano, largura_px, altura_px)
        
        # Converter para escala de cinza
        mosaico_gray = mosaico.convert('L')
        
        # Reduzir contraste/brilho
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(mosaico_gray)
        mosaico_dark = enhancer.enhance(0.4)
        enhancer = ImageEnhance.Contrast(mosaico_dark)
        mosaico_final = enhancer.enhance(0.7)
        mosaico_final = mosaico_final.convert('RGB')
        
        # Salvar em buffer
        img_buffer = BytesIO()
        mosaico_final.save(img_buffer, format='JPEG', quality=90)
        img_buffer.seek(0)
        
        # Desenhar mosaico
        self.canvas.drawImage(
            ImageReader(img_buffer),
            0, 0,
            width=self.largura_pagina,
            height=self.altura_pagina
        )
        
        # Adicionar título do ano
        self.canvas.setFillColor('white')
        
        # Título
        self.canvas.setFont('Helvetica-Bold', 56)
        titulo_w = self.canvas.stringWidth(titulo_ano, 'Helvetica-Bold', 56)
        self.canvas.drawString(
            (self.largura_pagina - titulo_w) / 2,
            self.altura_pagina * 0.55,
            titulo_ano
        )
        
        # Ano
        if ano:
            self.canvas.setFont('Helvetica', 36)
            texto_ano = f"~ {ano}"
            ano_w = self.canvas.stringWidth(texto_ano, 'Helvetica', 36)
            self.canvas.drawString(
                (self.largura_pagina - ano_w) / 2,
                self.altura_pagina * 0.42,
                texto_ano
            )
        
        self.canvas.showPage()
        self.numero_pagina += 1
    
    def criar_contra_capa(self):
        """
        Cria a contra capa (última página).
        Usa imagem pré-gerada se existir em _capas/contra_capa.jpg
        """
        # Verificar se existe contra capa pré-gerada
        contra_capa_path = self.pasta_raiz / "_capas" / "contra_capa.jpg"
        
        if contra_capa_path.exists():
            # Usar contra capa pré-gerada (já tem texto e estilo aplicados)
            self.canvas.drawImage(
                str(contra_capa_path),
                0, 0,
                width=self.largura_pagina,
                height=self.altura_pagina,
                preserveAspectRatio=False
            )
            self.canvas.showPage()
            return
        
        # Fallback: gerar contra capa dinamicamente
        # Fundo branco (já é o padrão)
        
        # Texto centralizado
        self.canvas.setFillColor('black')
        
        # Nome
        self.canvas.setFont('Helvetica-Bold', 32)
        texto1 = "Bruno Sereia Broering"
        texto1_w = self.canvas.stringWidth(texto1, 'Helvetica-Bold', 32)
        self.canvas.drawString(
            (self.largura_pagina - texto1_w) / 2,
            self.altura_pagina * 0.55,
            texto1
        )
        
        # Período
        self.canvas.setFont('Helvetica', 24)
        texto2 = "Infantil 2021 ~ 2025"
        texto2_w = self.canvas.stringWidth(texto2, 'Helvetica', 24)
        self.canvas.drawString(
            (self.largura_pagina - texto2_w) / 2,
            self.altura_pagina * 0.45,
            texto2
        )
        
        self.canvas.showPage()
    
    def gerar(self) -> bool:
        """
        Gera o fotolivro completo com capa, subcapas, conteúdo e contra capa.
        
        Retorna True se bem-sucedido, False caso contrário.
        """
        # Validar estrutura
        if not self.validar_estrutura():
            return False
        
        # Nota: ajustes do usuário devem ser passados via construtor (ajustes_usuario)
        # ou através do sistema de schema (schema_fotolivro.json)
        
        # Criar canvas do PDF
        try:
            self.canvas = canvas.Canvas(
                str(self.arquivo_saida),
                pagesize=(self.largura_pagina, self.altura_pagina)
            )
        except Exception as e:
            print(f"ERRO: Não foi possível criar o arquivo PDF: {e}")
            return False
        
        # Primeiro, carregar todas as fotos para criar a capa
        print("Carregando fotos...")
        todas_fotos = []
        fotos_por_ano = {}
        
        for nome_pasta in PASTAS_ANOS:
            pasta = encontrar_pasta_ano(self.pasta_raiz, nome_pasta)
            if pasta is None:
                continue
            
            caminhos_imagens = listar_imagens(pasta)
            if not caminhos_imagens:
                print(f"AVISO: Nenhuma imagem encontrada em {nome_pasta}, pulando...")
                continue
            
            fotos = [FotoInfo(caminho) for caminho in caminhos_imagens]
            fotos_por_ano[nome_pasta] = fotos
            todas_fotos.extend(fotos)
        
        if not todas_fotos:
            print("ERRO: Nenhuma foto encontrada!")
            return False
        
        print(f"Total de fotos carregadas: {len(todas_fotos)}")
        
        # Criar capa principal
        print("Criando capa...")
        self.criar_capa(todas_fotos)
        
        total_paginas = 1  # Capa
        
        # Processar cada pasta (ano) na ordem fixa
        for nome_pasta in PASTAS_ANOS:
            if nome_pasta not in fotos_por_ano:
                continue
            
            fotos = fotos_por_ano[nome_pasta]
            
            # Criar subcapa do ano
            print(f"Criando subcapa para {nome_pasta}...")
            self.criar_subcapa(fotos, nome_pasta)
            total_paginas += 1
            
            # Agrupar fotos em páginas
            grupos = self.agrupar_fotos(fotos)
            
            # Adicionar cada grupo como uma página
            for grupo in grupos:
                self.adicionar_pagina(grupo)
                total_paginas += 1
        
        # Criar contra capa
        print("Criando contra capa...")
        self.criar_contra_capa()
        total_paginas += 1
        
        # Finalizar PDF
        try:
            self.canvas.save()
        except Exception as e:
            print(f"ERRO: Não foi possível salvar o PDF: {e}")
            return False
        
        print(f"\n✓ Fotolivro gerado com sucesso!")
        print(f"  Total de fotos: {len(todas_fotos)}")
        print(f"  Total de páginas: {total_paginas}")
        print(f"  Arquivo salvo em: {self.arquivo_saida.absolute()}")
        
        return True


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal do script."""
    if len(sys.argv) != 3:
        print("Uso: python fotolivro.py <pasta_raiz> <arquivo_saida.pdf>")
        print("\nExemplo:")
        print("  python fotolivro.py ./fotos_bruno ./fotolivro_bruno.pdf")
        sys.exit(1)
    
    pasta_raiz = Path(sys.argv[1])
    arquivo_saida = Path(sys.argv[2])
    
    # Garantir que a extensão do arquivo de saída seja .pdf
    if arquivo_saida.suffix.lower() != '.pdf':
        arquivo_saida = arquivo_saida.with_suffix('.pdf')
    
    # Gerar fotolivro
    gerador = GeradorFotolivro(pasta_raiz, arquivo_saida)
    sucesso = gerador.gerar()
    
    if not sucesso:
        sys.exit(1)


if __name__ == "__main__":
    main()

