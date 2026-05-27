from pdfrw import PdfReader, PdfWriter, PdfDict, PageMerge
from pdfrw.objects.pdfobject import PdfObject
import pandas as pd
from datetime import datetime
import re
from reportlab.pdfgen import canvas
from io import BytesIO

# =====================================================
# LINKS GOOGLE SHEETS
# =====================================================

base_id = "1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Beneficiarios"
url_unimed = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=483371263"
url_produtos = "https://docs.google.com/spreadsheets/d/1KcdNWj-qrvaHSoqKNEA0gNvwWzGuRQoD/export?format=csv&gid=680489316"

# =====================================================
# FUNÇÕES
# =====================================================

def limpar_df(df):
    df = df.fillna("")
    df.columns = df.columns.astype(str).str.strip()

    for coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.strip()

    return df


def somente_digitos(valor, tamanho=None):
    valor = "" if pd.isna(valor) else str(valor)
    valor = "".join(filter(str.isdigit, valor))

    if tamanho:
        valor = valor.zfill(tamanho)

    return valor


def nome_seguro(texto):
    return re.sub(r'[\\/*?:"<>|]', "-", str(texto))


def formatar_data(valor):
    valor = str(valor).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%Y-%m-%d"
    ]

    for formato in formatos:
        try:
            data = datetime.strptime(valor, formato)
            return data.strftime("%d/%m/%Y")
        except:
            pass

    return valor


def calcular_idade(data_nascimento):
    data_nascimento = formatar_data(data_nascimento)

    try:
        nascimento = datetime.strptime(data_nascimento, "%d/%m/%Y")
        hoje = datetime.today()

        idade = hoje.year - nascimento.year

        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1

        return idade

    except:
        return 0


def converter_valor(valor):
    valor = str(valor).replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except:
        return 0.0


def formatar_moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_por_extenso(mes):
    meses = {
        "1": "Janeiro",
        "2": "Fevereiro",
        "3": "Março",
        "4": "Abril",
        "5": "Maio",
        "6": "Junho",
        "7": "Julho",
        "8": "Agosto",
        "9": "Setembro",
        "10": "Outubro",
        "11": "Novembro",
        "12": "Dezembro",
    }

    mes = str(mes).strip().replace(".0", "")
    return meses.get(mes, mes)


def buscar_valor_por_idade(produto_base, idade):
    produto_base = produto_base.copy()

    produto_base["Faixa-Inicio"] = (
        produto_base["Faixa-Inicio"]
        .astype(str)
        .str.replace(",", ".")
        .astype(float)
    )

    produto_base["Faixa-Fim"] = (
        produto_base["Faixa-Fim"]
        .astype(str)
        .str.replace(",", ".")
        .astype(float)
    )

    linha = produto_base[
        (produto_base["Faixa-Inicio"] <= idade) &
        (produto_base["Faixa-Fim"] >= idade)
    ]

    if linha.empty:
        return 0.0

    return converter_valor(linha.iloc[0]["Valor"])


# =====================================================
# LER BASES
# =====================================================

print("1 - Lendo Beneficiários")
clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))

print("2 - Lendo Unimeds")
unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))

print("3 - Lendo Produtos")
produtos = limpar_df(pd.read_csv(url_produtos, dtype=str))

print("4 - Bases carregadas")

# =====================================================
# ENTRADAS
# =====================================================

codigo = input("Digite o código do cliente: ").strip()

print("\nTipo de processo:")
print("1 - Troca de produto")
print("2 - Troca de instituição")
print("3 - Inclusão de dependente")

tipo_opcao = input("\nDigite a opção: ").strip()

tipos = {
    "1": "Troca de produto",
    "2": "Troca de instituição",
    "3": "Inclusão de dependente"
}

tipo_processo = tipos.get(tipo_opcao)

if not tipo_processo:
    print("Tipo de processo inválido.")
    exit()

data_vigencia = input("Digite a data de vigência (DD/MM/AA): ").strip()
produto_escolhido = input("Digite o nome completo do produto: ").strip()

cpf_novo_dependente = ""

if tipo_processo == "Inclusão de dependente":
    cpf_novo_dependente = input("Digite o CPF do novo dependente: ").strip()

if tipo_processo == "Troca de instituição":
    nova_instituicao = input("Digite o nome da nova instituição: ").strip()
    novo_cnpj_instituicao = input("Digite o CNPJ da nova instituição: ").strip()
else:
    nova_instituicao = ""
    novo_cnpj_instituicao = ""

# =====================================================
# DATA VIGÊNCIA DD/MM/AA
# =====================================================

data_partes = data_vigencia.split("/")

dia_vigencia = data_partes[0] if len(data_partes) > 0 else ""
mes_vigencia = data_partes[1] if len(data_partes) > 1 else ""
ano_vigencia = data_partes[2][-2:] if len(data_partes) > 2 else ""

# =====================================================
# BUSCAR TITULAR
# =====================================================

cliente = clientes[
    (clientes["CODIGO"] == codigo) &
    (clientes["TIPO"] == "T")
]

if cliente.empty:
    print("Titular não encontrado.")
    exit()

row = cliente.iloc[0]

# =====================================================
# BUSCAR DEPENDENTES
# =====================================================

if tipo_processo == "Inclusão de dependente":

    cpf_limpo = somente_digitos(cpf_novo_dependente, 11)

    dependentes = clientes[
        clientes["CPF"].apply(lambda x: somente_digitos(x, 11)) == cpf_limpo
    ]

    if dependentes.empty:
        print("Dependente não encontrado pelo CPF informado.")
        exit()

else:

    dependentes = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

# =====================================================
# BUSCAR PRODUTO
# =====================================================

produto_base = produtos[
    produtos["Produto"].str.strip().str.upper() == produto_escolhido.upper()
]

if produto_base.empty:
    print("Produto não encontrado.")
    exit()

produto_row = produto_base.iloc[0]

# =====================================================
# BUSCAR OPERADORA DO CLIENTE
# =====================================================

nome_operadora_cliente = str(row["OPERADORA"]).strip().upper()

unimeds.columns = unimeds.columns.astype(str).str.strip()

coluna_unimed = None

for col in unimeds.columns:
    if col.strip().upper() == "UNIMED":
        coluna_unimed = col
        break

if coluna_unimed is None:
    print("Coluna Unimed não encontrada.")
    exit()

unimeds[coluna_unimed] = (
    unimeds[coluna_unimed]
    .astype(str)
    .str.strip()
    .str.upper()
)

unimed = unimeds[
    unimeds[coluna_unimed].apply(
        lambda x: str(x).strip().upper() in nome_operadora_cliente
        or nome_operadora_cliente in str(x).strip().upper()
    )
]

if unimed.empty:
    print("Operadora não encontrada na aba Unimed.")
    print("Nome buscado:", nome_operadora_cliente)
    exit()

unimed_row = unimed.iloc[0]

# =====================================================
# INSTITUIÇÃO / AGLUTINADORA
# =====================================================

if tipo_processo == "Troca de instituição":
    instituicao = nova_instituicao
    cnpj_instituicao = somente_digitos(novo_cnpj_instituicao, 14)
else:
    instituicao = row["INSTITUICAO"]
    cnpj_instituicao = somente_digitos(row["CNPJ_INSTITUICAO"], 14)

# =====================================================
# CARÊNCIAS
# =====================================================

if tipo_processo in ["Troca de produto", "Troca de instituição"]:
    carencia_titular = "sequência/troca"
    carencia_dependente = "sequência/troca"
else:
    carencia_titular = "sequência"
    carencia_dependente = "sequência/troca"

# =====================================================
# BENEFICIÁRIOS E VALORES
# =====================================================

beneficiarios = []

idade_titular = calcular_idade(row["DATA NASC."])
valor_titular = buscar_valor_por_idade(produto_base, idade_titular)

beneficiarios.append({
    "tipo": "Titular",
    "nome": row["NOME"],
    "cpf": somente_digitos(row["CPF"], 11),
    "rg": row["RG"],
    "data_nasc": formatar_data(row["DATA NASC."]),
    "mae": row["NOME DA MAE"],
    "parentesco": "TITULAR",
    "naturalidade": row["NATURALIDADE"],
    "sexo": row["SEXO"],
    "estado_civil": row["ESTADO CIVIL"],
    "idade": idade_titular,
    "valor": valor_titular,
    "carencia": carencia_titular
})

for _, dep in dependentes.iterrows():

    idade_dep = calcular_idade(dep["DATA NASC."])
    valor_dep = buscar_valor_por_idade(produto_base, idade_dep)

    beneficiarios.append({
        "tipo": "Dependente",
        "nome": dep["NOME"],
        "cpf": somente_digitos(dep["CPF"], 11),
        "rg": dep["RG"],
        "data_nasc": formatar_data(dep["DATA NASC."]),
        "mae": dep["NOME DA MAE"],
        "parentesco": dep["GRAU DE PARENTESCO"],
        "naturalidade": dep["NATURALIDADE"],
        "sexo": dep["SEXO"],
        "estado_civil": dep["ESTADO CIVIL"],
        "idade": idade_dep,
        "valor": valor_dep,
        "carencia": carencia_dependente
    })

valor_total = sum(b["valor"] for b in beneficiarios)

# =====================================================
# ABRIR PDF
# =====================================================

pdf = PdfReader("proposta_adesao.pdf")

if pdf.Root.AcroForm:
    pdf.Root.AcroForm.update(
        PdfDict(NeedAppearances=PdfObject("true"))
    )

# =====================================================
# CAMPOS PDF
# =====================================================

campos_pdf = {
    "Texto11": dia_vigencia,
    "Texto12": mes_vigencia,
    "Texto13": ano_vigencia,

    "Aglutinadora": instituicao,
    "CNPJ": cnpj_instituicao,

    "Operadora": unimed_row[coluna_unimed],
    "CNPJ_2": somente_digitos(unimed_row["CNPJ"], 14),
    "Registro ANS": unimed_row["ANS"],

    "Razão Social": row["EMPRESA"],
    "CNPJ_3": somente_digitos(row["CNPJ"], 14),
    "Modalidade": produto_row["Tipo Cont"],

    "Nome Completo": row["NOME"],
    "CPF": somente_digitos(row["CPF"], 11),
    "RG": row["RG"],
    "Data de Nascimento": formatar_data(row["DATA NASC."]),
    "Nome da Mãe": row["NOME DA MAE"],
    "Naturalidade": row["NATURALIDADE"],
    "Sexo": row["SEXO"],
    "Estado Civil": row["ESTADO CIVIL"],
    "Cartão Nacional de Saúde  CNS": "",
    "Carência": carencia_titular,

    "DDDTelefone Residencial": "",
    "DDDTelefone Celular": row["TELEFONE"],
    "Email": row["EMAIL"],

    "Nome Completo_2": "",
    "CPF_2": "",
    "RG_2": "",
    "Email_2": "",
    "Sexo_2": "",
    "Estado Civil_2": "",

    "Local Data": row["CIDADE"],
    "Titular Responsável Legal ou Financeiro": row["NOME"],

    "Plano": produto_row["Produto"],
    "Registro na ANS": produto_row["No. Registro"],

    "O mês de reajuste será": mes_por_extenso(produto_row["MesReajs"]),
    "Valor total das Mensalidades R 000": formatar_moeda(valor_total),

    "Texto35": row["CIDADE"],
    "Texto36": datetime.today().strftime("%d/%m/%Y"),
}

# =====================================================
# DEPENDENTES PÁGINA 2
# =====================================================

dependente_campos = [
    {
        "nome": "Nome Completo_3",
        "cpf": "CPF_3",
        "rg": "RG_3",
        "data": "Data de Nascimento_2",
        "mae": "Nome da Mãe_2",
        "parentesco": "Parentesco",
        "naturalidade": "Naturalidade_2",
        "sexo": "Sexo_3",
        "estado": "Estado Civil_3",
        "cns": "Cartão Nacional de Saúde  CNS_2",
        "carencia": "Carência_2"
    },
    {
        "nome": "Nome Completo_4",
        "cpf": "CPF_4",
        "rg": "RG_4",
        "data": "Data de Nascimento_3",
        "mae": "Nome da Mãe_3",
        "parentesco": "Parentesco_2",
        "naturalidade": "Naturalidade_3",
        "sexo": "Sexo_4",
        "estado": "Estado Civil_4",
        "cns": "Cartão Nacional de Saúde  CNS_3",
        "carencia": "Carência_3"
    },
    {
        "nome": "Nome Completo_5",
        "cpf": "CPF_5",
        "rg": "RG_5",
        "data": "Data de Nascimento_4",
        "mae": "Nome da Mãe_4",
        "parentesco": "Parentesco_3",
        "naturalidade": "Naturalidade_4",
        "sexo": "Sexo_5",
        "estado": "Estado Civil_5",
        "cns": "Cartão Nacional de Saúde  CNS_4",
        "carencia": "Carência_4"
    },
    {
        "nome": "Nome Completo_6",
        "cpf": "CPF_6",
        "rg": "RG_6",
        "data": "Data de Nascimento_5",
        "mae": "Nome da Mãe_5",
        "parentesco": "Parentesco_4",
        "naturalidade": "Naturalidade_5",
        "sexo": "Sexo_6",
        "estado": "Estado Civil_6",
        "cns": "Cartão Nacional de Saúde  CNS_5",
        "carencia": "Carência_5"
    },
]

dependentes_apenas = beneficiarios[1:]

for i, dep in enumerate(dependentes_apenas[:4]):

    mapa = dependente_campos[i]

    campos_pdf[mapa["nome"]] = dep["nome"]
    campos_pdf[mapa["cpf"]] = dep["cpf"]
    campos_pdf[mapa["rg"]] = dep["rg"]
    campos_pdf[mapa["data"]] = dep["data_nasc"]
    campos_pdf[mapa["mae"]] = dep["mae"]
    campos_pdf[mapa["parentesco"]] = dep["parentesco"]
    campos_pdf[mapa["naturalidade"]] = dep["naturalidade"]
    campos_pdf[mapa["sexo"]] = dep["sexo"]
    campos_pdf[mapa["estado"]] = dep["estado_civil"]
    campos_pdf[mapa["cns"]] = ""
    campos_pdf[mapa["carencia"]] = dep["carencia"]

# =====================================================
# VALORES PÁGINA 4
# =====================================================

valores_pagina4 = [
    ("IdadeTitular", "R", "R_2"),
    ("IdadeDependente 1", "R_3", "R_4"),
    ("IdadeDependente 2", "R_5", "R_6"),
    ("IdadeDependente 3", "R_7", "R_8"),
    ("IdadeDependente 4", "R_9", "R_10"),
]

for i, b in enumerate(beneficiarios[:5]):

    campo_idade, campo_mensalidade, campo_taxa = valores_pagina4[i]

    campos_pdf[campo_idade] = str(b["idade"])
    campos_pdf[campo_mensalidade] = formatar_moeda(b["valor"])
    campos_pdf[campo_taxa] = "0,00"

# =====================================================
# PREENCHER CAMPOS EDITÁVEIS
# =====================================================

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
                PdfDict(V=str(campos_pdf[campo]))
            )

# =====================================================
# ESCREVER ENDEREÇO POR COORDENADAS COM PDFRW
# =====================================================

# =====================================================
# ESCREVER ENDEREÇO POR COORDENADAS COM PDFRW
# =====================================================

packet = BytesIO()

largura = float(pdf.pages[0].MediaBox[2])
altura = float(pdf.pages[0].MediaBox[3])

can = canvas.Canvas(packet, pagesize=(largura, altura))

can.setFont("Helvetica", 10)

# Página 1 - endereço do titular
can.drawString(295, 281, str(row["ENDERECO"]))          # Endereço
can.drawString(35, 250, str(row["NUMERO"]))             # Número
can.drawString(145, 245, str(row["COMPLEMENTO"]))       # Complemento
can.drawString(300, 250, str(row["BAIRRO"]))            # Bairro
can.drawString(35, 215, str(row["CIDADE"]))             # Município
can.drawString(385, 215, somente_digitos(row["CEP"], 8))# CEP
can.drawString(500, 215, str(row["UF"]))                # UF

can.save()

packet.seek(0)

overlay_pdf = PdfReader(packet)

PageMerge(pdf.pages[0]).add(overlay_pdf.pages[0]).render()

# =====================================================
# SALVAR PDF FINAL
# =====================================================

nome_pdf_final = f"Proposta_Adesao_{codigo}_{nome_seguro(row['NOME'])}.pdf"

PdfWriter().write(nome_pdf_final, pdf)

print(f"\nPDF FINAL GERADO: {nome_pdf_final}")