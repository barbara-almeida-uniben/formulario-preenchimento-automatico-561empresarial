import streamlit as st
import pandas as pd

from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject

# =====================================================
# CONFIG STREAMLIT
# =====================================================

st.set_page_config(
    page_title="Gerador de Formulário",
    layout="centered"
)

st.title("Gerador de Formulário Cancelamento 561 - Empresarial")

# =====================================================
# LER PLANILHAS
# =====================================================

base_id = "1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Beneficiarios"
url_unimed = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Unimed"

clientes = pd.read_csv(
    url_beneficiarios,
    dtype=str
).fillna("")

clientes.columns = clientes.columns.str.strip()

unimeds = pd.read_csv(
    url_unimed,
    dtype=str
).fillna("")

unimeds.columns = unimeds.columns.str.strip()

for coluna in clientes.columns:
    clientes[coluna] = clientes[coluna].astype(str).str.strip()

for coluna in unimeds.columns:
    unimeds[coluna] = unimeds[coluna].astype(str).str.strip()

# =====================================================
# MOTIVOS
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

# =====================================================
# INPUTS
# =====================================================

codigo = st.text_input(
    "Digite o código do cliente"
)

motivo = st.selectbox(
    "Motivo do cancelamento",
    list(motivos.keys()),
    format_func=lambda x: f"{x} - {motivos[x]}"
)

# =====================================================
# BOTÃO
# =====================================================

if st.button("Gerar PDF"):

    # =================================================
    # BUSCAR TITULAR
    # =================================================

    cliente = clientes[
        (clientes['CODIGO'] == codigo) &
        (clientes['TIPO'] == 'T')
    ]

    if cliente.empty:

        st.error("Titular não encontrado.")
        st.stop()

    row = cliente.iloc[0]

    st.write("Instituição:", row['INSTITUICAO'])
    st.write("CNPJ Instituição:", row['CNPJ_INSTITUICAO'])

    # =================================================
    # BUSCAR DEPENDENTES ATIVOS
    # =================================================

    dependentes = clientes[
        (clientes['CODIGO'] == codigo) &
        (clientes['TIPO'] == 'D') &
        (clientes['STATUS'] == 'A')
    ]

    # =================================================
    # BUSCAR UNIMED
    # =================================================

    # =================================================
    # BUSCAR UNIMED
    # =================================================

    # Normalizar nomes das colunas
    unimeds.columns = unimeds.columns.astype(str).str.strip()

    # Encontrar automaticamente a coluna da Unimed
    coluna_unimed = None

    for col in unimeds.columns:
        if col.strip().upper() == "UNIMED":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        st.error("Coluna 'Unimed' não encontrada na aba Unimed.")
        st.write("Colunas encontradas:", unimeds.columns.tolist())
        st.stop()

    nome_unimed = str(row['OPERADORA']).strip().upper()

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed].str.contains(nome_unimed, na=False, regex=False)
    ]

    if unimed.empty:
        st.error("Unimed não encontrada.")
        st.write("Nome buscado:", nome_unimed)
        st.write("Unimeds cadastradas:", unimeds[coluna_unimed].tolist())
        st.stop()

    unimed_row = unimed.iloc[0]

    # =================================================
    # ABRIR PDF
    # =================================================

    pdf = PdfReader("formulario.pdf")

    # =================================================
    # HABILITAR APPEARANCE
    # =================================================

    if pdf.Root.AcroForm:

        pdf.Root.AcroForm.update(
            PdfDict(
                NeedAppearances=PdfObject('true')
            )
        )

    # =================================================
    # LISTA BENEFICIÁRIOS
    # =================================================

    beneficiarios = []

    beneficiarios.append(row['NOME'])

    for _, dep in dependentes.iterrows():

        beneficiarios.append(dep['NOME'])

    # =================================================
    # CAMPOS PDF
    # =================================================

    campos_pdf = {

        # =============================================
        # OPERADORA
        # =============================================

        "Texto3": unimed_row['Unimed'],
        "Texto4": unimed_row['CNPJ'],
        "Texto5": unimed_row['ANS'],

        # =============================================
        # AGLUTINADORA
        # =============================================

        "Texto42": row['INSTITUICAO'],
        "Texto43": row['CNPJ_INSTITUICAO'],

        # =============================================
        # EMPRESA ADERENTE
        # =============================================

        "Razão Social": row['EMPRESA'],
        "CNPJ": row['CNPJ'],

        # =============================================
        # TITULAR
        # =============================================

        "Texto7": row['NOME'],
        "Texto8": row['CPF'],
        "Texto9": row['EMAIL'],

        "Texto10": row['ENDERECO'],
        "Texto11": row['NUMERO'],

        "Bairro": row['COMPLEMENTO'],
        "Texto12": row['BAIRRO'],

        "Texto13": row['CIDADE'],
        "UF": row['UF'],
        "CEP": row['CEP'],

        "DDD  Telefone Celular": row['TELEFONE'],

        # =============================================
        # MOTIVO CANCELAMENTO
        # =============================================

        "Texto16": motivo,
        "Texto18": row['NOME'],

        # =============================================
        # PÁGINA 3
        # =============================================

        "estou ciente das informações acima prestadas e manifesto a minha vontade em": row['NOME'],
        "undefined_4": row['CPF'],

        # =============================================
        # DEPENDENTES
        # =============================================

        "Texto1": beneficiarios[0] if len(beneficiarios) > 0 else "",
        "Texto2": beneficiarios[1] if len(beneficiarios) > 1 else "",

        "Nomes": beneficiarios[0] if len(beneficiarios) > 0 else "",
        "undefined_11": beneficiarios[1] if len(beneficiarios) > 1 else "",
        "undefined_12": beneficiarios[2] if len(beneficiarios) > 2 else "",
        "undefined_13": beneficiarios[3] if len(beneficiarios) > 3 else "",

        "Nomes_2": beneficiarios[4] if len(beneficiarios) > 4 else "",
        "undefined_14": beneficiarios[5] if len(beneficiarios) > 5 else "",
        "undefined_15": beneficiarios[6] if len(beneficiarios) > 6 else "",
        "undefined_16": beneficiarios[7] if len(beneficiarios) > 7 else ""

    }

    # =================================================
    # PREENCHER PDF
    # =================================================

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

            # IGNORAR CHECKBOX E RADIO
            if "Check Box" in campo:
                continue

            if "Group" in campo:
                continue

            # PREENCHER
            if campo in campos_pdf:

                annotation.update(
                    PdfDict(
                        V=str(campos_pdf[campo])
                    )
                )

    # =================================================
    # SALVAR PDF
    # =================================================

    nome_pdf = f"{row['NOME']}.pdf"

    PdfWriter().write(
        nome_pdf,
        pdf
    )

    # =================================================
    # DOWNLOAD
    # =================================================

    with open(nome_pdf, "rb") as file:

        st.download_button(
            label="⬇️ Baixar PDF",
            data=file,
            file_name=nome_pdf,
            mime="application/pdf"
        )

    st.success("PDF gerado com sucesso!")