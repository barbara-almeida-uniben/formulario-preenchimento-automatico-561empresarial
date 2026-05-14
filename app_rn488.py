import streamlit as st
import pandas as pd
from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
from datetime import datetime
import calendar
import os
import re
import zipfile

st.set_page_config(
    page_title="RN488",
    layout="centered"
)

st.title("📄 Gerador RN488")
st.write("Solicitação de Exclusão de Beneficiários")

base_id = "1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Beneficiarios"

url_unimed = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=483371263"

url_lote = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=448530069"


def limpar_df(df):
    df = df.fillna("")
    df.columns = df.columns.astype(str).str.strip()

    for coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.strip()

    return df


def nome_seguro(texto):
    return re.sub(r'[\\/*?:"<>|]', "-", str(texto))


def somente_digitos(valor, tamanho=None):
    valor = "" if pd.isna(valor) else str(valor)
    valor = "".join(filter(str.isdigit, valor))

    if tamanho:
        valor = valor.zfill(tamanho)

    return valor


clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))
unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))

modo = st.radio(
    "Como deseja gerar?",
    ["Individual", "Lote"]
)


def gerar_pdf_rn488(
    codigo,
    registro_produto,
    data_rescisao
):

    hoje = datetime.today()

    data_solicitacao = hoje.strftime("%d/%m/%Y")

    ultimo_dia = calendar.monthrange(
        hoje.year,
        hoje.month
    )[1]

    data_exclusao = f"{ultimo_dia:02d}/{hoje.month:02d}/{hoje.year}"

    cliente = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        return None, f"Titular não encontrado para código {codigo}"

    row = cliente.iloc[0]

    dependentes = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

    dependentes_nomes = dependentes["NOME"].tolist()

    nome_unimed = str(
        row["OPERADORA"]
    ).strip().upper()

    unimeds.columns = (
        unimeds.columns
        .astype(str)
        .str.strip()
    )

    coluna_unimed = None

    for col in unimeds.columns:
        if col.strip().upper() == "UNIMED":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        return None, "Coluna 'Unimed' não encontrada."

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed]
        .str.contains(
            nome_unimed,
            na=False,
            regex=False
        )
    ]

    if unimed.empty:
        return None, f"Unimed não encontrada para {row['NOME']}"

    unimed_row = unimed.iloc[0]

    pdf = PdfReader("formulario_rn488.pdf")

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(
            PdfDict(
                NeedAppearances=PdfObject("true")
            )
        )

    campos_pdf = {
        # OPERADORA
        "Texto1": unimed_row[coluna_unimed],
        "Texto2": somente_digitos(
            unimed_row["CNPJ"],
            14
        ),
        "Texto3": unimed_row["ANS"],

        # CONTRATANTE
        "Razão Social": row["EMPRESA"],
        "CNPJ": somente_digitos(
            row["CNPJ"],
            14
        ),

        # TITULAR
        "Texto6": row["NOME"],
        "Texto7": somente_digitos(
            row["CPF"],
            11
        ),

        # REGISTRO PRODUTO
        "Texto5": registro_produto,

        # DEPENDENTES
        "D1 Nome": (
            dependentes_nomes[0]
            if len(dependentes_nomes) > 0
            else ""
        ),

        "D2 Nome": (
            dependentes_nomes[1]
            if len(dependentes_nomes) > 1
            else ""
        ),

        "Texto14": (
            dependentes_nomes[2]
            if len(dependentes_nomes) > 2
            else ""
        ),

        "D4 Nome": (
            dependentes_nomes[3]
            if len(dependentes_nomes) > 3
            else ""
        ),

        # DATAS
        "Data da rescisão do contrato de trabalho": data_rescisao,

        "Texto18": "Sócio-proprietário",

        "Texto19": "",

        "Texto20": data_solicitacao,

        "Texto4": data_exclusao,
    }

    for page in pdf.pages:

        annotations = page.get("/Annots")

        if not annotations:
            continue

        for annotation in annotations:

            if annotation.get("/Subtype") != "/Widget":
                continue

            key = annotation.get("/T")

            if not key:
                continue

            campo = key[1:-1]

            if "Check Box" in campo:
                continue

            if campo in campos_pdf:

                annotation.update(
                    PdfDict(
                        V=str(campos_pdf[campo])
                    )
                )

    nome_pdf = (
        f"RN488_{codigo}_"
        f"{nome_seguro(row['NOME'])}.pdf"
    )

    PdfWriter().write(
        nome_pdf,
        pdf
    )

    return nome_pdf, None


# =====================================================
# INDIVIDUAL
# =====================================================

if modo == "Individual":

    codigo = st.text_input(
        "Digite o código do cliente"
    )

    registro_produto = st.text_input(
        "Digite o Nº de Registro do Produto"
    )

    data_rescisao = st.text_input(
        "Digite a data da rescisão - DD/MM/AAAA"
    )

    if st.button("Gerar PDF individual"):

        if (
            not codigo
            or not registro_produto
            or not data_rescisao
        ):

            st.error("Preencha todos os campos.")

        else:

            arquivo, erro = gerar_pdf_rn488(
                codigo.strip(),
                registro_produto.strip(),
                data_rescisao.strip()
            )

            if erro:
                st.error(erro)

            else:

                st.success(
                    "PDF gerado com sucesso!"
                )

                with open(arquivo, "rb") as file:

                    st.download_button(
                        label="⬇️ Baixar PDF",
                        data=file,
                        file_name=arquivo,
                        mime="application/pdf"
                    )

# =====================================================
# LOTE
# =====================================================

else:

    st.info(
        "O modo lote lê a aba Lote_RN488 da planilha."
    )

    if st.button("Gerar PDFs em lote"):

        lote = limpar_df(
            pd.read_csv(
                url_lote,
                dtype=str
            )
        )

        pasta_saida = "PDFs_RN488"

        os.makedirs(
            pasta_saida,
            exist_ok=True
        )

        arquivos_gerados = []

        for _, item in lote.iterrows():

            codigo = item["CODIGO"]

            registro_produto = item[
                "REGISTRO_PRODUTO"
            ]

            data_rescisao = item[
                "DATA_RESCISAO"
            ]

            arquivo, erro = gerar_pdf_rn488(
                codigo,
                registro_produto,
                data_rescisao
            )

            if erro:
                st.warning(erro)
                continue

            caminho_final = os.path.join(
                pasta_saida,
                arquivo
            )

            if os.path.exists(caminho_final):
                os.remove(caminho_final)

            os.replace(
                arquivo,
                caminho_final
            )

            arquivos_gerados.append(
                caminho_final
            )

        if not arquivos_gerados:

            st.error(
                "Nenhum PDF foi gerado."
            )

            st.stop()

        nome_zip = "PDFs_RN488.zip"

        with zipfile.ZipFile(
            nome_zip,
            "w"
        ) as zipf:

            for arquivo in arquivos_gerados:

                zipf.write(
                    arquivo,
                    os.path.basename(arquivo)
                )

        st.success(
            f"{len(arquivos_gerados)} PDF(s) gerado(s) com sucesso!"
        )

        with open(nome_zip, "rb") as file:

            st.download_button(
                label="⬇️ Baixar ZIP com PDFs",
                data=file,
                file_name=nome_zip,
                mime="application/zip"
            )