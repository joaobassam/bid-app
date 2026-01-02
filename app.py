import os
import glob
import zipfile
import pandas as pd
import streamlit as st


# =========================
# CONFIG
# =========================
# Padrão: pega todos os arquivos no formato bid*.csv.zip (bid.csv.zip, bid2.csv.zip, ...)
ZIP_GLOB_PATTERN = "bid*.csv.zip"

# Se quiser travar uma lista fixa (em vez de auto-descobrir), preencha e use.
# Ex.: FIXED_ZIPS = ["bid.csv.zip", "bid2.csv.zip", "bid3.csv.zip"]
FIXED_ZIPS = None  # ou uma lista


# =========================
# NORMALIZAÇÃO DE COLUNAS
# =========================
def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe o DataFrame original do CSV e renomeia as colunas
    para nomes 'padrão' usados no app.
    """
    col_map = {}
    for orig in df.columns:
        low = str(orig).strip().lower()

        if "nome" in low and "completo" in low:
            col_map[orig] = "nome_completo"
        elif "inscri" in low:  # INSCRIÇÃO / INSCRICAO
            col_map[orig] = "inscricao"
        elif "contrato" in low:
            col_map[orig] = "contrato"
        elif "início" in low or "inicio" in low:
            col_map[orig] = "inicio"
        elif low == "data" or "data " in low:
            col_map[orig] = "data"
        elif "cbf" in low:
            col_map[orig] = "cbf"
        elif "apelido" in low:
            col_map[orig] = "apelido"
        elif "nascimento" in low:
            col_map[orig] = "nascimento"
        elif "time" in low or "clube" in low or "equipe" in low:
            col_map[orig] = "time"
        elif "idade" in low:
            col_map[orig] = "idade"

    df = df.rename(columns=col_map)

    colunas_esperadas = [
        "nome_completo",
        "inscricao",
        "contrato",
        "data",
        "inicio",
        "cbf",
        "apelido",
        "nascimento",
        "time",
        "idade",
    ]
    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[colunas_esperadas]
    return df


# =========================
# DESCOBRIR FONTES
# =========================
def discover_zip_files() -> list[str]:
    """
    Retorna uma lista de arquivos .zip a serem carregados.
    Por padrão, auto-descobre com glob (bid*.csv.zip), mas você pode fixar via FIXED_ZIPS.
    """
    if isinstance(FIXED_ZIPS, list) and FIXED_ZIPS:
        return [z for z in FIXED_ZIPS if os.path.exists(z)]

    zips = sorted(glob.glob(ZIP_GLOB_PATTERN))
    return zips


def file_signature(path: str) -> tuple:
    """
    Assinatura simples para invalidar cache quando o arquivo muda.
    """
    try:
        stt = os.stat(path)
        return (os.path.basename(path), stt.st_size, int(stt.st_mtime))
    except FileNotFoundError:
        return (os.path.basename(path), 0, 0)


# =========================
# CARREGAR DADOS (MULTI-ZIP)
# =========================
def _find_csv_inside_zip(z: zipfile.ZipFile) -> str:
    """
    Encontra o CSV dentro do ZIP. Prioriza *.csv.
    """
    names = z.namelist()
    csvs = [n for n in names if n.lower().endswith(".csv")]
    if not csvs:
        raise FileNotFoundError("Nenhum arquivo .csv encontrado dentro do ZIP.")
    # Se tiver mais de um, pega o primeiro em ordem alfabética
    return sorted(csvs)[0]


@st.cache_data
def load_data(zip_paths: tuple, signatures: tuple):
    """
    Lê vários ZIPs e concatena em um único DataFrame.
    `signatures` serve só para o cache perceber mudanças nos arquivos.
    """
    frames = []

    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path, "r") as z:
            csv_inside = _find_csv_inside_zip(z)
            with z.open(csv_inside) as f:
                df_part = pd.read_csv(f, sep=",", dtype=str)

        df_part = normalizar_colunas(df_part)

        # garantir tudo como string para evitar problemas
        for c in df_part.columns:
            df_part[c] = df_part[c].astype("string")

        # opcional: registrar fonte (ajuda debug e auditoria)
        df_part["__fonte_zip"] = os.path.basename(zip_path)

        frames.append(df_part)

    if not frames:
        raise FileNotFoundError(
            f"Nenhum arquivo encontrado. Esperado algo como '{ZIP_GLOB_PATTERN}' no diretório do app."
        )

    df = pd.concat(frames, ignore_index=True)
    return df


@st.cache_data
def get_times(df):
    series = df["time"].dropna().astype(str).str.strip()
    series = series[series != ""]
    return sorted(series.unique())


@st.cache_data
def search_jogadores(df, nome_busca, time_filtro, limite=200):
    df2 = df

    if nome_busca:
        nome_busca = nome_busca.strip()
        mask_nome = df2["nome_completo"].str.contains(nome_busca, case=False, na=False)
        mask_apelido = df2["apelido"].str.contains(nome_busca, case=False, na=False)
        df2 = df2[mask_nome | mask_apelido]

    if time_filtro and time_filtro != "Todos":
        df2 = df2[df2["time"] == time_filtro]

    cols = [
        "nome_completo",
        "apelido",
        "time",
        "idade",
        "nascimento",
        "contrato",
        "inicio",
        "data",
        "inscricao",
        "cbf",
    ]
    df2 = df2[cols]

    df2 = df2.sort_values("nome_completo").head(limite)
    return df2


@st.cache_data
def get_detalhes_jogador(df, nome_parte):
    df2 = df
    nome_parte = nome_parte.strip()
    mask = df2["nome_completo"].str.contains(nome_parte, case=False, na=False)
    df2 = df2[mask]

    cols = [
        "nome_completo",
        "apelido",
        "time",
        "idade",
        "nascimento",
        "contrato",
        "inicio",
        "data",
        "inscricao",
        "cbf",
    ]
    df2 = df2[cols]

    df2 = df2.sort_values(["nome_completo", "data", "inicio"])
    return df2


# =========================
# APP PRINCIPAL
# =========================
def main():
    st.set_page_config(page_title="Consulta BID", layout="wide")

    st.title("📚 Banco BID – Consulta e Detalhes de Jogadores (CSV)")
    st.write(
        "Interface web usando múltiplos arquivos `bid*.csv.zip` (ex.: `bid.csv.zip`, `bid2.csv.zip`, ...)."
    )

    zip_files = discover_zip_files()
    signatures = tuple(file_signature(p) for p in zip_files)

    # carregar dados
    try:
        df = load_data(tuple(zip_files), signatures)
    except Exception as e:
        st.error(f"Erro ao carregar dados do CSV: {e}")
        st.stop()

    st.caption(f"Arquivos carregados: {len(zip_files)} | Linhas totais: {len(df):,}".replace(",", "."))

    # Abas principais
    aba_consulta, aba_detalhes = st.tabs(["🔍 Consulta", "🧑‍💼 Detalhes do jogador"])

    # ----------------- ABA CONSULTA -----------------
    with aba_consulta:
        st.subheader("Consulta geral")

        st.sidebar.header("Filtros – Consulta geral")

        nome_busca = st.sidebar.text_input(
            "Buscar por nome ou apelido",
            help="Digite parte do nome ou apelido do jogador (ex: 'SILVA', 'RONALDO')."
        )

        # carregar lista de times
        try:
            times = get_times(df)
        except Exception as e:
            st.sidebar.error(f"Erro ao carregar lista de times: {e}")
            times = []

        opcoes_times = ["Todos"] + times
        time_filtro = st.sidebar.selectbox("Filtrar por time (Consulta)", opcoes_times)

        limite = st.sidebar.slider(
            "Limite de resultados (Consulta)",
            min_value=50,
            max_value=1000,
            value=200,
            step=50,
            help="Número máximo de linhas exibidas na tabela de consulta."
        )

        st.sidebar.markdown("---")
        st.sidebar.info("Use os filtros e clique em **Buscar (Consulta)** para ver os resultados.")

        if st.sidebar.button("Buscar (Consulta)"):
            df_res = search_jogadores(df, nome_busca, time_filtro, limite=limite)

            st.subheader("Resultados da busca (Consulta geral)")

            if df_res.empty:
                st.warning("Nenhum registro encontrado com os filtros informados.")
            else:
                st.write(f"Registros encontrados: **{len(df_res)}** (limite {limite})")
                st.dataframe(df_res, use_container_width=True)

                csv_out = df_res.to_csv(index=False, sep=";").encode("utf-8-sig")
                st.download_button(
                    "⬇️ Baixar resultados em CSV",
                    data=csv_out,
                    file_name="resultado_bid_consulta.csv",
                    mime="text/csv",
                )
        else:
            st.info("Na aba **Consulta**, use os filtros na barra lateral e clique em **Buscar (Consulta)**.")

    # ----------------- ABA DETALHES DO JOGADOR -----------------
    with aba_detalhes:
        st.subheader("Detalhes do jogador")

        st.write(
            "Digite **parte do nome completo** do jogador para ver o histórico de registros "
            "(times, datas, contratos, etc.)."
        )

        nome_parte = st.text_input(
            "Nome do jogador (ou parte)",
            help="Exemplos: 'JOÃO', 'SILVA', 'NUNES'. A busca é feita em `nome_completo`."
        )

        buscar_detalhes = st.button("Buscar detalhes")

        if buscar_detalhes:
            if not nome_parte.strip():
                st.warning("Digite ao menos parte do nome do jogador para buscar.")
            else:
                df_det = get_detalhes_jogador(df, nome_parte.strip())

                if df_det.empty:
                    st.warning("Nenhum jogador encontrado com esse nome.")
                else:
                    nomes_unicos = df_det["nome_completo"].dropna().unique()

                    st.write(f"Jogadores encontrados: **{len(nomes_unicos)}**")
                    st.write("Clique em cada nome abaixo para ver os detalhes:")

                    for nome in nomes_unicos:
                        sub = df_det[df_det["nome_completo"] == nome]

                        apelidos = sub["apelido"].dropna().unique()
                        times_jog = sub["time"].dropna().unique()
                        idades = sub["idade"].dropna().unique()
                        nascimentos = sub["nascimento"].dropna().unique()

                        with st.expander(f"{nome}", expanded=False):
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**Apelido(s):**")
                                st.write(", ".join(str(a) for a in apelidos) if len(apelidos) else "-")

                                st.markdown("**Idade(s) registrada(s):**")
                                st.write(", ".join(str(i) for i in idades) if len(idades) else "-")

                                st.markdown("**Data(s) de nascimento registrada(s):**")
                                st.write(", ".join(str(n) for n in nascimentos) if len(nascimentos) else "-")

                            with col2:
                                st.markdown("**Times com registro:**")
                                st.write(", ".join(str(t) for t in times_jog) if len(times_jog) else "-")

                            st.markdown("---")
                            st.markdown("**Histórico de registros no BID:**")

                            tabela_hist = sub[
                                [
                                    "time",
                                    "contrato",
                                    "inicio",
                                    "data",
                                    "inscricao",
                                    "cbf",
                                    "idade",
                                    "nascimento",
                                    "apelido",
                                ]
                            ]

                            st.dataframe(tabela_hist, use_container_width=True)

                            csv_jogador = tabela_hist.to_csv(index=False, sep=";").encode("utf-8-sig")
                            st.download_button(
                                f"⬇️ Baixar histórico de {nome} em CSV",
                                data=csv_jogador,
                                file_name=f"historico_{nome.replace(' ', '_')}.csv",
                                mime="text/csv",
                                key=f"download_{nome}",
                            )
        else:
            st.info(
                "Na aba **Detalhes do jogador**, digite parte do nome e clique em **Buscar detalhes** "
                "para ver o histórico completo."
            )


if __name__ == "__main__":
    main()
