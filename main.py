from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
import pandas as pd

# =====================================================
# LER PLANILHAS
# =====================================================

clientes = pd.read_excel(
    "dados.xlsx",
    sheet_name="Beneficiarios",
    dtype=str
).fillna("")

unimeds = pd.read_excel(
    "dados.xlsx",
    sheet_name="Unimed",
    dtype=str
).fillna("")

# =====================================================
# LIMPAR ESPAÇOS
# =====================================================

for coluna in clientes.columns:
    clientes[coluna] = clientes[coluna].astype(str).str.strip()

for coluna in unimeds.columns:
    unimeds[coluna] = unimeds[coluna].astype(str).str.strip()

# =====================================================
# BUSCAR CLIENTE
# =====================================================

codigo = input("Digite o código do cliente: ")

cliente = clientes[
    (clientes['CODIGO'] == codigo) &
    (clientes['TIPO'] == 'T')
]

if cliente.empty:

    print("Titular não encontrado.")
    exit()

row = cliente.iloc[0]

# =====================================================
# BUSCAR DEPENDENTES ATIVOS
# =====================================================

dependentes = clientes[
    (clientes['CODIGO'] == codigo) &
    (clientes['TIPO'] == 'D') &
    (clientes['STATUS'] == 'A')
]

# =====================================================
# MOTIVO CANCELAMENTO
# =====================================================

motivos = {
    "76": "Óbito",
    "64": "Não usa o plano",
    "58": "Migração para outra operadora",
    "60": "Insatisfeito com o atendimento do plano",
    "95": "Pessoal",
    "82": "Financeiro",
    "75": "Troca na mesma Unimed",
    "56": "Viagem/Mudança"
}

print("\nQual o motivo do cancelamento?\n")

for codigo_motivo, descricao in motivos.items():

    print(f"{codigo_motivo} - {descricao}")

motivo_escolhido = input(
    "\nDigite o código do motivo: "
)

if motivo_escolhido not in motivos:

    print("Motivo inválido.")
    exit()

# =====================================================
# BUSCAR UNIMED
# =====================================================

nome_unimed = row['OPERADORA'].strip().upper()

unimeds['Unimed'] = unimeds['Unimed'].str.strip().str.upper()

unimed = unimeds[
    unimeds['Unimed'] == nome_unimed
]

if unimed.empty:

    print("Unimed não encontrada.")
    exit()

unimed_row = unimed.iloc[0]

# =====================================================
# ABRIR PDF
# =====================================================

pdf = PdfReader("formulario.pdf")

# =====================================================
# HABILITAR APPEARANCE
# =====================================================

if pdf.Root.AcroForm:

    pdf.Root.AcroForm.update(
        PdfDict(
            NeedAppearances=PdfObject('true')
        )
    )

# =====================================================
# LISTA BENEFICIÁRIOS
# =====================================================

beneficiarios = []

# TITULAR PRIMEIRO
beneficiarios.append(row['NOME'])

# DEPENDENTES
for _, dep in dependentes.iterrows():

    beneficiarios.append(dep['NOME'])

# =====================================================
# DICIONÁRIO CAMPOS PDF
# =====================================================

campos_pdf = {

    # =================================================
    # OPERADORA
    # =================================================

    "Texto3": unimed_row['Unimed'],
    "Texto4": unimed_row['CNPJ'],
    "Texto5": unimed_row['ANS'],

    # =================================================
    # AGLUTINADORA
    # =================================================

    "Texto42": row['INSTITUICAO'],
    "Texto43": row['CNPJ_INSTITUICAO'],

    # =================================================
    # EMPRESA ADERENTE
    # =================================================

    "Razão Social": row['EMPRESA'],
    "CNPJ": row['CNPJ'],

    # =================================================
    # TITULAR
    # =================================================

    "Texto7": row['NOME'],
    "Texto8": row['CPF'],
    "Texto9": row['EMAIL'],

    "Texto10": row['ENDERECO'],
    "Texto11": row['NUMERO'],

    # COMPLEMENTO / BAIRRO
    "Bairro": row['COMPLEMENTO'],
    "Texto12": row['BAIRRO'],

    "Texto13": row['CIDADE'],
    "UF": row['UF'],
    "CEP": row['CEP'],

    "DDD  Telefone Celular": row['TELEFONE'],

    # =================================================
    # MOTIVO CANCELAMENTO
    # =================================================

    "Texto16": motivo_escolhido,
    "Texto18": row['NOME'],

    # =================================================
    # PÁGINA 3
    # =================================================

    "estou ciente das informações acima prestadas e manifesto a minha vontade em": row['NOME'],
    "undefined_4": row['CPF'],

    # =================================================
    # DEPENDENTES
    # =================================================

    # PÁGINA 4
    "Texto1": beneficiarios[0] if len(beneficiarios) > 0 else "",
    "Texto2": beneficiarios[1] if len(beneficiarios) > 1 else "",

    # PÁGINA 5
    "Nomes": beneficiarios[0] if len(beneficiarios) > 0 else "",
    "undefined_11": beneficiarios[1] if len(beneficiarios) > 1 else "",
    "undefined_12": beneficiarios[2] if len(beneficiarios) > 2 else "",
    "undefined_13": beneficiarios[3] if len(beneficiarios) > 3 else "",

    "Nomes_2": beneficiarios[4] if len(beneficiarios) > 4 else "",
    "undefined_14": beneficiarios[5] if len(beneficiarios) > 5 else "",
    "undefined_15": beneficiarios[6] if len(beneficiarios) > 6 else "",
    "undefined_16": beneficiarios[7] if len(beneficiarios) > 7 else ""
}

# =====================================================
# PREENCHER PDF
# =====================================================

for page in pdf.pages:

    annotations = page.get('/Annots')

    if not annotations:
        continue

    for annotation in annotations:

        if annotation.get('/Subtype') != '/Widget':
            continue

        key = annotation.get('/T')

        if not key:
            continue

        campo = key[1:-1]

        # IGNORAR CHECKBOX
        if "Check Box" in campo:
            continue

        # IGNORAR RADIO BUTTON
        if "Group" in campo:
            continue

        # PREENCHER
        if campo in campos_pdf:

            annotation.update(
                PdfDict(
                    V=str(campos_pdf[campo])
                )
            )

# =====================================================
# SALVAR PDF
# =====================================================

nome_pdf = f"{row['NOME']}.pdf"

PdfWriter().write(
    nome_pdf,
    pdf
)

print(f"\nPDF gerado com sucesso: {nome_pdf}")