# PRP – Geração de Fotolivro em PDF (A4 Paisagem, 1–3 fotos por página, 5 pastas/anos)

## Papel da IA

Você é um assistente de programação especializado em automação de tarefas gráficas para impressão.  
Sua tarefa é gerar **um script completo** que monte um **fotolivro em PDF** a partir de fotos organizadas em 5 pastas (uma por ano do Infantil).

O output deve ser um **script pronto para uso**, bem comentado, com instruções claras de execução em linha de comando.

---

## Contexto

- Vou montar um **fotolivro** para a formatura do meu filho.
- As fotos estarão organizadas em **5 pastas**, cada uma representando um ano:
  - `Infantil1`
  - `Infantil2`
  - `Infantil3`
  - `Infantil4`
  - `Infantil5`
- Dentro de cada pasta haverá várias fotos **já selecionadas**, mas:
  - **a ordem interna de cada pasta é livre**,
  - o script pode organizar/agrupá-las da forma que fizer **mais sentido esteticamente**.
- A **ordem global** do fotolivro precisa seguir estritamente a sequência dos anos:

  > Infantil1 → Infantil2 → Infantil3 → Infantil4 → Infantil5

- Quero usar **1, 2 ou no máximo 3 fotos por página**, otimizando:
  - quantidade de páginas,
  - estética da página,
  - respeito à sequência dos anos.

Não quero pagar por ferramentas, nem ficar arrastando foto em editor.

---

## Objetivo

Gerar um **script de linha de comando** que:

1. Leia as imagens de **5 pastas** (Infantil1 a Infantil5), sempre na sequência **fixa** dos anos.
2. Dentro de cada ano, agrupe as fotos em páginas com **1, 2 ou 3 fotos**, usando layouts bonitos e proporcionais.
3. Crie um **PDF em formato A4 paisagem**, com:
   - bordas brancas ao redor das fotos,
   - **margem maior na lombada** alternando entre páginas pares e ímpares.
4. Preserve a **proporção das fotos** (sem distorção), usando “contain” dentro de cada área de foto.
5. Gere um PDF adequado para **impressão em alta qualidade**.

---

## Linguagem e Bibliotecas

- **Linguagem preferencial**: Python 3.
- Biblioteca sugerida para o PDF: **ReportLab**.
- Pode usar bibliotecas de imagem (ex.: Pillow) se precisar para ler metadados/dimensões.

No topo do script, incluir instruções de instalação, por exemplo:

```bash
pip install reportlab
# se usar Pillow:
pip install pillow
```

---

## Estrutura de Pastas e Ordem dos Anos

### Estrutura esperada

O script deve receber um **diretório raiz** que contenha **exatamente 5 subpastas**, com estes nomes (case-insensitive aceitável, mas documente):

- `Infantil1`
- `Infantil2`
- `Infantil3`
- `Infantil4`
- `Infantil5`

Exemplo:

```text
/raiz_fotos/
  Infantil1/
    foto1.jpg
    foto2.jpg
    ...
  Infantil2/
    ...
  Infantil3/
    ...
  Infantil4/
    ...
  Infantil5/
    ...
```

### Ordem obrigatória

- O fotolivro deve ser montado **sempre** na seguinte sequência:

  1. Todas as páginas geradas a partir das fotos de `Infantil1`
  2. Em seguida, todas as páginas geradas a partir de `Infantil2`
  3. Depois `Infantil3`
  4. Depois `Infantil4`
  5. Por fim, `Infantil5`

- **Dentro de cada pasta**, o script pode:
  - ordenar as fotos por nome, **mas** está autorizado a **reorganizar/agrupá-las** em páginas de 1, 2 ou 3 fotos de um jeito que fique visualmente mais coerente (por proporção/orientação).
  - Ou seja: a “história” é respeitada pelo bloco do ano, não necessariamente pela ordem nominal dos arquivos.

Se houver fotos em mais ou menos pastas, o script deve:

- avisar o usuário (por exemplo: “não encontrei a pasta Infantil3”),
- e falhar de forma clara, a menos que o programador opte por tornar isso opcional (explique em comentários).

---

## Especificação Técnica da Página

### Formato da Página

- Tamanho: **A4** em **modo paisagem**.
- A4: 210 × 297 mm (retrato) → em paisagem: **297 (largura) × 210 (altura) mm**.
- Trabalhar em **points**: 72 points = 1 inch.
- Incluir uma função `mm_to_points(mm)`.

### Margens

Definir margens em milímetros, convertendo para points:

- **Margem externa mínima (todos os lados)**: ~10 mm.
- **Margem extra de lombada**: ~7 mm adicionais no lado da lombada.
- **Espaço interno (bordinha entre área útil e fotos)**: ~3 mm.
- **Espaço entre fotos na mesma página**: ~3–5 mm (definir e explicar no código).

Regra de lombada:

- Considerar numeração de página em **1-based** (página 1, 2, 3…).
- **Página 1 é direita** (como num livro aberto):
  - Página 1 → **lombada à esquerda** (margem esquerda maior).
  - Página 2 → **lombada à direita**.
  - Página 3 → **lombada à esquerda**.
  - Página 4 → **lombada à direita**.
  - … alternando.

---

## Imagens: Entrada e Classificação

- Formatos aceitos (pode ajustar):  
  `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp`.
- Dentro de cada pasta de ano:
  - ler todos os arquivos de imagem válidos,
  - opcionalmente ordenar por nome,
  - mas a **organização em páginas é livre**, com base na proporção/orientação das fotos.

Para cada imagem, o script deve:

- obter largura e altura em pixels,
- classificar como:
  - **paisagem** (largura > altura),
  - **retrato** (altura > largura),
  - **quase quadrada** (proporção próxima de 1:1, por exemplo entre 0,9 e 1,1).

---

## Layouts de 1, 2 ou 3 Fotos por Página

### Área útil da página

Para cada página:

1. Calcular área útil (sem margens externas + lombada + bordinha interna).
2. Dentro dessa área útil, dividir em sub-áreas conforme o layout escolhido.

### Layouts

**Layout 1 – 1 foto (L1)**  
- Foto ocupa praticamente toda a área útil, com bordas brancas.
- Usado quando:
  - só sobra 1 foto no final de um ano,
  - ou a heurística decidir que ela merece destaque (não precisa ser sofisticado, mas documentar a regra).

**Layout 2 – 2 fotos (L2)**  
Ter pelo menos dois subtipos:

- **L2H (horizontal)** – 2 fotos lado a lado:
  - 2 colunas na área útil, mesma altura.
  - bom para duas fotos **paisagem** ou proporções similares.

- **L2V (vertical)** – 2 fotos empilhadas:
  - 2 linhas na área útil, mesma largura.
  - bom para duas fotos **retrato** ou bem altas.

**Layout 3 – 3 fotos (L3)**  
Pelo menos duas variações:

- **L3A – 2 em cima, 1 embaixo**:
  - topo: 2 fotos lado a lado,
  - embaixo: 1 foto centralizada.

- **L3B – 1 em cima, 2 embaixo**:
  - topo: 1 foto centralizada,
  - embaixo: 2 fotos lado a lado.

O código deve:

- definir explicitamente as coordenadas de cada sub-área (box) para cada layout,
- comentar essas definições para facilitar ajustes.

---

## Lógica de Agrupamento por Ano (1–3 fotos por página)

Para **cada pasta (ano)**, seguir um fluxo como:

1. Obter lista de imagens do ano.
2. Se quiser, ordenar por nome (para ter previsibilidade).
3. Percorrer a lista de imagens com um índice.
4. Em cada passo, olhar **até 3 fotos à frente** (se existirem).
5. Decidir formar grupos de tamanho 1, 2 ou 3 com base em:
   - quantas fotos ainda restam,
   - orientações/proporções das próximas imagens,
   - layouts disponíveis (L1, L2H, L2V, L3A, L3B).

Exemplo de heurística simples:

- Se restam **3 ou mais fotos**:
  - tentar formar grupo de 3 se elas tiverem proporções que encaixam num layout L3 razoável,
  - senão, formar grupo de 2.
- Se restam **2 fotos**:
  - formar grupo de 2 e escolher entre L2H ou L2V conforme proporção.
- Se resta **1 foto**:
  - formar grupo de 1 (L1).

A IA deve especificar uma lógica clara e implementá-la no código, mesmo que não seja “perfeita de design”, mas coerente e previsível.

---

## Ajuste das Fotos nas Sub-áreas

Para cada foto em sua sub-área (box):

1. Calcular `ratio_img = largura_img / altura_img`.
2. Calcular `ratio_box = largura_box / altura_box`.
3. Ajustar a foto em modo “contain”:

   - Se `ratio_img >= ratio_box`:
     - limitar pela **largura** da box,
     - calcular altura proporcional,
     - sobram bordas em cima/baixo.
   - Caso contrário:
     - limitar pela **altura** da box,
     - calcular largura proporcional,
     - sobram bordas nas laterais.

4. Centralizar a foto na box:
   - `x = x_box + (largura_box - largura_foto_redimensionada) / 2`
   - `y = y_box + (altura_box - altura_foto_redimensionada) / 2`.

---

## Resolução / Qualidade

- O script deve:
  - gerar página A4 com dimensões físicas corretas,
  - posicionar cada imagem na escala adequada, sem upscaling absurdo.
- Não é obrigatório setar explicitamente “300 dpi” nos metadados, mas garantir:
  - que a página está em A4,
  - que as fotos mantêm sua resolução original (ou apenas redução, não aumento exagerado).
- Se a biblioteca permitir, ajustar compressão dos JPEGs para boa qualidade.

---

## Interface de Linha de Comando

O script deve ser executado com a seguinte interface:

```bash
python fotolivro.py <pasta_raiz> <arquivo_saida.pdf>
```

Exemplo:

```bash
python fotolivro.py ./fotos_bruno ./fotolivro_bruno.pdf
```

Onde:

- `<pasta_raiz>` contém as subpastas `Infantil1` a `Infantil5`.

Requisitos:

- Se `<pasta_raiz>` não existir, exibir erro claro.
- Se alguma das pastas `Infantil1`…`Infantil5` não existir, avisar claramente.
- Se uma pasta existir, mas não tiver imagens válidas, avisar.
- Ao final, imprimir mensagem informando o caminho do PDF gerado.

---

## Tratamento de Erros e Robustez

- Mensagens de erro em **português**, objetivas.
- Exemplos:
  - “Pasta raiz não encontrada: …”
  - “Pasta Infantil3 não encontrada dentro de: …”
  - “Nenhuma imagem válida encontrada na pasta Infantil2.”

---

## Documentação e Comentários

- Comentar as partes importantes do código:
  - descoberta das pastas dos anos,
  - ordem fixa dos anos,
  - cálculo de margens e lombada,
  - lógica de agrupamento (1–3 fotos por página) **por ano**,
  - seleção de layout (L1, L2H, L2V, L3A, L3B),
  - redimensionamento e centralização das fotos.
- No início do arquivo, deixar um comentário em linguagem simples explicando:
  - o que o script faz,
  - como preparar as pastas,
  - como executar.

---

## Saída Esperada da IA

- Entregar o **código completo do script** em um único bloco de código.
- Linguagem: **Python 3**, seguindo as regras acima.
- O código deve ser autoexplicativo via comentários; não é necessário texto extra fora do bloco de código.
