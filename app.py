import io
import zipfile
import pandas as pd
import streamlit as st

ZIP_PATH = "bid.csv.zip"   # arquivo zip subido no GitHub
CSV_NAME_INSIDE_ZIP = "bid.csv"  # nome do CSV dentro do ZIP


# ---------------- CARREGAR DADOS ----------------

@st.cache_data
def load_data():
    """
    Lê o arquivo bid.csv de dentro do bid.csv.zip
    e devolve um DataFrame pandas.
    """
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        with z.open(CSV_NAME_INSIDE_ZIP) as f:
            # ajuste o 'sep' se necessário: ';' ou ','
            df = pd.read_csv(f, sep=",", dtype=str)  # tudo como texto para evitar problemas
    # padronizar nomes de colunas (se quiser garantir):
    df.columns = [c.strip().lower() for c in df.columns]

    # aqui assumo que as colunas têm esses nomes:
    # nome_completo, inscricao, contrato, data, inicio,
    # cbf, apelido, nascimento, time, idade
    # se forem diferentes, me manda que eu ajusto
    return df


@st.cache_data
def get_times(df):
    series = df["time"].dropna().astype(str).str.strip()
    series = series[series != ""]
    return sorted(series.unique())


@st.cache_data
def search_jogadores(df, nome_busca, time_filtro, limite=200):
    df2 = df.copy()

    # filtro por nome / apelido (contendo texto)
    if nome_busca:
        nome_busca = nome_busca.strip()
        mask_nome = df2["nome_completo"].str.contains(nome_busca, case=False, na=False)
        mask_apelido = df2["apelido"].str.contains(nome_busca, case=False, na=False)
        df2 = df2[mask_nome | mask_apelido]

    # filtro por time
    if time_filtro and time_filtro != "Todos":
        df2 = df2[df2["time"] == time_filtro]

    # selecionar colunas na ordem desejada
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
    df2 = df.copy()
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


# ---------------- APP PRINCIPAL ----------------

def main():
    st.set_page_config(page_title="Consulta BID", layout="wide")

    st.title("📚 Banco BID – Consulta e Detalhes de Jogadores (CSV)")
    st.write("Interface web usando dados do arquivo `bid.csv` compactado em `bid.csv.zip`.")

    # carregar dados
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados do CSV: {e}")
        st.stop()

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

                # opção para exportar
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
                    nomes_unicos = df_det["nome_completo"].unique()

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

