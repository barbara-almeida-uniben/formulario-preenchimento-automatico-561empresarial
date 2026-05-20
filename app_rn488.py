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
st.write("Solicitação de Exclusão de Beneficiários + Termo de Responsabilidade Financeira")

# =====================================================
# LINKS GOOGLE SHEETS
# =====================================================

base_id = "1KcdNWj-qrvaHSoqKNEA0gNvwWzGuRQoD"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Beneficiarios"

url_unimed = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=483371263"

url_lote = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=110582"


# =====================================================
# FUNÇÕES
# =====================================================

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


def data_curta(data):
    data = str(data).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%m/%d/%Y"
    ]

    for formato in formatos:
        try:
            return datetime.strptime(data, formato).strftime("%d/%m/%y")
        except:
            pass

    partes = data.split("/")

    if len(partes) == 3:
        return f"{partes[0]}/{partes[1]}/{partes[2][-2:]}"

    return data


def mes_extenso(numero_mes):
    meses = {
        1: "janeiro",
        2: "fevereiro",
        3: "março",
        4: "abril",
        5: "maio",
        6: "junho",
        7: "julho",
        8: "agosto",
        9: "setembro",
        10: "outubro",
        11: "novembro",
        12: "dezembro"
    }

    return meses.get(int(numero_mes), "")


def marcar_checkbox(annotation):
    annotation.update(
        PdfDict(
            V=PdfObject("/Yes"),
            AS=PdfObject("/Yes")
        )
    )


# =====================================================
# CARREGAR BASES
# =====================================================

clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))
unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))


# =====================================================
# GERAR RN488
# =====================================================

def gerar_pdf_rn488(codigo, registro_produto, data_rescisao, motivo_desligamento):

    hoje = datetime.today()

    data_solicitacao = hoje.strftime("%d/%m/%y")

    ultimo_dia = calendar.monthrange(
        hoje.year,
        hoje.month
    )[1]

    data_exclusao = f"{ultimo_dia:02d}/{hoje.month:02d}/{str(hoje.year)[-2:]}"

    cliente = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        return None, None, f"Titular não encontrado para código {codigo}"

    row = cliente.iloc[0]

    dependentes = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

    dependentes_nomes = dependentes["NOME"].tolist()

    nome_unimed = str(row["OPERADORA"]).strip().upper()

    unimeds.columns = unimeds.columns.astype(str).str.strip()

    coluna_unimed = None

    for col in unimeds.columns:
        if col.strip().upper() == "UNIMED":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        return None, None, "Coluna 'Unimed' não encontrada."

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed].apply(
            lambda x: str(x).strip().upper() in nome_unimed
            or nome_unimed in str(x).strip().upper()
        )
    ]

    if unimed.empty:
        return None, None, f"Unimed não encontrada para {row['NOME']} - {nome_unimed}"

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
        "Texto2": somente_digitos(unimed_row["CNPJ"], 14),
        "Texto3": unimed_row["ANS"],

        # CONTRATANTE
        "Razão Social": row["EMPRESA"],
        "CNPJ": somente_digitos(row["CNPJ"], 14),

        # TITULAR
        "Texto6": row["NOME"],
        "Texto7": somente_digitos(row["CPF"], 11),

        # REGISTRO PRODUTO
        "Texto5": registro_produto,

        # DEPENDENTES
        "D1 Nome": dependentes_nomes[0] if len(dependentes_nomes) > 0 else "",
        "D2 Nome": dependentes_nomes[1] if len(dependentes_nomes) > 1 else "",
        "Texto14": dependentes_nomes[2] if len(dependentes_nomes) > 2 else "",
        "D4 Nome": dependentes_nomes[3] if len(dependentes_nomes) > 3 else "",

        # DATAS
        "Data da rescisão do contrato de trabalho": data_curta(data_rescisao),
        "Texto18": "Sócio-proprietário",
        "Texto19": "",
        "Texto20": data_solicitacao,
        "Texto4": data_exclusao,
    }

    motivo = str(motivo_desligamento).strip().upper()

    mapa_motivo_checkbox = {
        "SEM JUSTA CAUSA": "Check Box8",
        "COM JUSTA CAUSA": "Check Box10",
        "PEDIDO DE DEMISSAO": "Check Box11",
        "PEDIDO DE DEMISSÃO": "Check Box11",
    }

    checkbox_motivo = mapa_motivo_checkbox.get(motivo)

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

            if campo in campos_pdf:

                annotation.update(
                    PdfDict(
                        V=str(campos_pdf[campo])
                    )
                )

            if checkbox_motivo and campo == checkbox_motivo:
                marcar_checkbox(annotation)

    nome_pdf = (
        f"RN488_{codigo}_"
        f"{nome_seguro(row['NOME'])}.pdf"
    )

    PdfWriter().write(
        nome_pdf,
        pdf
    )

    return nome_pdf, row, None


# =====================================================
# GERAR TERMO RESPONSABILIDADE FINANCEIRA
# =====================================================

def gerar_termo_resp_financeira(codigo, row):

    hoje = datetime.today()

    dia_atual = hoje.strftime("%d")
    mes_atual = mes_extenso(hoje.month)
    ano_atual = str(hoje.year)

    mes_vigente = mes_extenso(hoje.month)
    ano_vigente = str(hoje.year)

    pdf = PdfReader("termo_resp_financeira.pdf")

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(
            PdfDict(
                NeedAppearances=PdfObject("true")
            )
        )

    campos_termo = {
        # Empresa
        "Texto1": row["EMPRESA"],

        # Mês e ano da responsabilidade financeira
        "do": mes_vigente,
        "sendo certo que a partir de tal data será de minha exclusiva responsabilidade o pagamento": ano_vigente,

        # Local e data
        "undefined": row["CIDADE"],
        "de": dia_atual,
        "de_2": mes_atual,
        "undefined_2": ano_atual,

        # CPF titular
        "Texto2": somente_digitos(row["CPF"], 11),

        # Assinatura em branco
        "Assinatura do funcionário": ""
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

            if campo in campos_termo:

                annotation.update(
                    PdfDict(
                        V=str(campos_termo[campo])
                    )
                )

    nome_pdf = (
        f"Termo_Resp_Financeira_{codigo}_"
        f"{nome_seguro(row['NOME'])}.pdf"
    )

    PdfWriter().write(
        nome_pdf,
        pdf
    )

    return nome_pdf


# =====================================================
# INTERFACE
# =====================================================

modo = st.radio(
    "Como deseja gerar?",
    ["Individual", "Lote"]
)


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
        "Digite a data da rescisão - DD/MM/AA"
    )

    motivo_desligamento = st.selectbox(
        "Motivo do desligamento",
        [
            "SEM JUSTA CAUSA",
            "COM JUSTA CAUSA",
            "PEDIDO DE DEMISSAO"
        ]
    )

    if st.button("Gerar documentos"):

        if (
            not codigo
            or not registro_produto
            or not data_rescisao
            or not motivo_desligamento
        ):

            st.error("Preencha todos os campos.")

        else:

            arquivo_rn488, row, erro = gerar_pdf_rn488(
                codigo.strip(),
                registro_produto.strip(),
                data_rescisao.strip(),
                motivo_desligamento.strip()
            )

            if erro:
                st.error(erro)

            else:

                arquivo_termo = gerar_termo_resp_financeira(
                    codigo.strip(),
                    row
                )

                nome_zip = f"Documentos_RN488_{codigo.strip()}.zip"

                with zipfile.ZipFile(nome_zip, "w") as zipf:
                    zipf.write(arquivo_rn488, os.path.basename(arquivo_rn488))
                    zipf.write(arquivo_termo, os.path.basename(arquivo_termo))

                st.success("Documentos gerados com sucesso!")

                with open(nome_zip, "rb") as file:

                    st.download_button(
                        label="⬇️ Baixar ZIP com RN488 + Termo",
                        data=file,
                        file_name=nome_zip,
                        mime="application/zip"
                    )


# =====================================================
# LOTE
# =====================================================

else:

    st.info(
        "O modo lote lê a aba Lote_RN488 da planilha."
    )

    st.write(
        "A aba deve conter as colunas: CODIGO, REGISTRO_PRODUTO, DATA_RESCISAO e MOTIVO_DESLIGAMENTO."
    )

    if st.button("Gerar documentos em lote"):

        lote = limpar_df(
            pd.read_csv(
                url_lote,
                dtype=str
            )
        )

        pasta_saida = "Documentos_RN488"

        os.makedirs(
            pasta_saida,
            exist_ok=True
        )

        # limpa arquivos antigos
        for arquivo_antigo in os.listdir(pasta_saida):
            caminho_antigo = os.path.join(pasta_saida, arquivo_antigo)

            if os.path.isfile(caminho_antigo):
                os.remove(caminho_antigo)

        arquivos_gerados = []

        for _, item in lote.iterrows():

            codigo = item["CODIGO"]

            registro_produto = item[
                "REGISTRO_PRODUTO"
            ]

            data_rescisao = item[
                "DATA_RESCISAO"
            ]

            motivo_desligamento = item[
                "MOTIVO_DESLIGAMENTO"
            ]

            arquivo_rn488, row, erro = gerar_pdf_rn488(
                codigo,
                registro_produto,
                data_rescisao,
                motivo_desligamento
            )

            if erro:
                st.warning(erro)
                continue

            arquivo_termo = gerar_termo_resp_financeira(
                codigo,
                row
            )

            caminho_rn488 = os.path.join(
                pasta_saida,
                arquivo_rn488
            )

            caminho_termo = os.path.join(
                pasta_saida,
                arquivo_termo
            )

            if os.path.exists(caminho_rn488):
                os.remove(caminho_rn488)

            if os.path.exists(caminho_termo):
                os.remove(caminho_termo)

            os.replace(
                arquivo_rn488,
                caminho_rn488
            )

            os.replace(
                arquivo_termo,
                caminho_termo
            )

            arquivos_gerados.append(
                caminho_rn488
            )

            arquivos_gerados.append(
                caminho_termo
            )

        if not arquivos_gerados:

            st.error(
                "Nenhum documento foi gerado."
            )

            st.stop()

        nome_zip = f"Documentos_RN488_{datetime.today().strftime('%Y%m%d_%H%M%S')}.zip"

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
            f"{len(arquivos_gerados)} documento(s) gerado(s) com sucesso!"
        )

        with open(nome_zip, "rb") as file:

            st.download_button(
                label="⬇️ Baixar ZIP com documentos",
                data=file,
                file_name=nome_zip,
                mime="application/zip"
            )