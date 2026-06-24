import streamlit as st
import pandas as pd
from pypdf import PdfReader, PdfWriter
import re

st.set_page_config(page_title="Formulário 561", layout="centered")

st.title("📄 Gerador de Formulário 561")

# =========================
# PLANILHA
# =========================
SHEET_ID = "1KcdNWj-qrvaHSoqKNEA0gNvwWzGuRQoD"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=2120607349"
url_unimed = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=912196708"


def limpar_df(df):
    df = df.fillna("")
    df.columns = df.columns.astype(str).str.strip()
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def somente_digitos(valor, tamanho=None):
    valor = "" if pd.isna(valor) else str(valor)
    valor = re.sub(r"\D", "", valor)
    if tamanho:
        valor = valor.zfill(tamanho)
    return valor


def nome_seguro(texto):
    return re.sub(r'[\\/*?:"<>|]', "-", str(texto))


# =========================
# CARREGAMENTO
# =========================
try:
    clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))
    unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))
except Exception as e:
    st.error("Erro ao carregar planilhas")
    st.exception(e)
    st.stop()


# =========================
# INPUTS
# =========================
codigo = st.text_input("Digite o código do cliente")

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

motivo = st.selectbox(
    "Motivo do cancelamento",
    list(motivos.keys()),
    format_func=lambda x: f"{x} - {motivos[x]}"
)


# =========================
# GERAR PDF
# =========================
if st.button("Gerar PDF"):

    if not codigo:
        st.warning("Informe o código do cliente.")
        st.stop()

    codigo = codigo.strip()

    cliente = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        st.error("Titular não encontrado.")
        st.stop()

    row = cliente.iloc[0]

    # =========================
    # DEPENDENTES
    # =========================
    dependentes = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

    beneficiarios = [row["NOME"]]

    for _, dep in dependentes.iterrows():
        if dep["NOME"]:
            beneficiarios.append(dep["NOME"])

    beneficiarios = beneficiarios[:8]

    # =========================
    # UNIMED
    # =========================
    nome_unimed = str(row.get("OPERADORA", "")).strip().upper()

    col_unimed = next((c for c in unimeds.columns if c.strip().upper() == "UNIMED"), None)

    if not col_unimed:
        st.error("Coluna UNIMED não encontrada.")
        st.stop()

    unimeds[col_unimed] = unimeds[col_unimed].astype(str).str.strip().str.upper()

    unimed = unimeds[unimeds[col_unimed].str.contains(nome_unimed, na=False)]

    if unimed.empty:
        st.error("Unimed não encontrada.")
        st.stop()

    unimed_row = unimed.iloc[0]


    # =========================
    # CAMPOS PDF
    # =========================
    campos_pdf = {
        "Texto3": unimed_row.get(col_unimed, ""),
        "Texto4": somente_digitos(unimed_row.get("CNPJ", ""), 14),
        "Texto5": unimed_row.get("ANS", ""),

        "Texto42": row.get("INSTITUICAO", ""),
        "Texto43": somente_digitos(row.get("CNPJ_INSTITUICAO", ""), 14),

        "Razão Social": row.get("EMPRESA", ""),
        "CNPJ": somente_digitos(row.get("CNPJ", ""), 14),

        "Texto7": row.get("NOME", ""),
        "Texto8": somente_digitos(row.get("CPF", ""), 11),
        "Texto9": row.get("EMAIL", ""),

        "Texto10": row.get("ENDERECO", ""),
        "Texto11": row.get("NUMERO", ""),

        "Texto12": row.get("BAIRRO", ""),
        "Texto13": row.get("CIDADE", ""),
        "UF": row.get("UF", ""),
        "CEP": somente_digitos(row.get("CEP", ""), 8),

        "DDD  Telefone Celular": row.get("TELEFONE", ""),

        "Texto16": motivo,
        "Texto18": beneficiarios[0] if len(beneficiarios) > 0 else "",
    }

    # dependentes extras
    mapping = [
        ("Texto20", "Texto22"),
        ("Texto24", "Texto26"),
        ("Texto28", "Texto30"),
        ("Texto32", "Texto34"),
    ]

    for i, (c1, c2) in enumerate(mapping, start=1):
        if len(beneficiarios) > i:
            campos_pdf[c1] = motivo
            campos_pdf[c2] = beneficiarios[i]


   # =========================
# PDF FILL (CORRIGIDO - COM AcroForm)
# =========================

reader = PdfReader("formulario.pdf")
writer = PdfWriter()

# copia páginas corretamente
writer.append_pages_from_reader(reader)

# 🔥 mantém o formulário original (ESSENCIAL)
if "/AcroForm" in reader.trailer["/Root"]:
    writer._root_object.update({
        "/AcroForm": reader.trailer["/Root"]["/AcroForm"]
    })

# preenche campos
writer.update_page_form_field_values(
    writer.pages,
    campos_pdf
)

# nome do arquivo
nome_pdf = f"Formulario_561_{codigo}_{nome_seguro(row['NOME'])}.pdf"

# salva
with open(nome_pdf, "wb") as f:
    writer.write(f)

st.success("PDF gerado com sucesso!")

with open(nome_pdf, "rb") as file:
    st.download_button(
        label="📥 Baixar PDF",
        data=file,
        file_name=nome_pdf,
        mime="application/pdf"
    )