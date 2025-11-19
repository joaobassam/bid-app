import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "base_bid.db"  # ajuste se o .db estiver em outro lugar


def get_connection():
    return sqlite3.connect(DB_PATH)


@st.cache_data
def get_times():
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT DISTINCT time FROM jogadores WHERE time IS NOT NULL AND TRIM(time) <> '' ORDER BY time",
            conn,
        )
    return df["time"].tolist()


@st.cache_data
def search_jogadores(nome_busca, time_filtro, limite=200):
    query = "SELECT nome_completo, apelido, time, idade, nascimento, contrato, inicio, data, inscricao, cbf FROM jogadores WHERE 1=1"
    params = []

    # filtro por nome / apelido (contendo texto)
    if nome_busca:
        query += " AND (nome_completo LIKE ? OR apelido LIKE ?)"
        like = f"%{nome_busca}%"
        params.extend([like, like])

    # filtro por time
    if time_filtro and time_filtro != "Todos":
        query += " AND time = ?"
        params.append(time_filtro)

    query += " ORDER BY nome_completo LIMIT ?"
    params.append(limite)

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    return df


def main():
    st.set_page_config(page_title="Consulta BID", layout="wide")

    st.title("🔍 Consulta ao Banco BID (SQLite)")
    st.write("Interface simples para consultar a tabela `jogadores` do arquivo `base_bid.db`.")

    # Sidebar - filtros
    st.sidebar.header("Filtros")

    nome_busca = st.sidebar.text_input(
        "Buscar por nome ou apelido",
        help="Digite parte do nome ou apelido do jogador (ex: 'SILVA', 'RONALDO')."
    )

    # carregar lista de times
    try:
        times = get_times()
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar times: {e}")
        times = []

    opcoes_times = ["Todos"] + times
    time_filtro = st.sidebar.selectbox("Filtrar por time", opcoes_times)

    limite = st.sidebar.slider(
        "Limite de resultados",
        min_value=50,
        max_value=1000,
        value=200,
        step=50,
        help="Número máximo de linhas exibidas na tabela."
    )

    st.sidebar.markdown("---")
    st.sidebar.info("Dica: use os filtros para reduzir o volume de resultados.")

    # Botão de busca
    if st.sidebar.button("Buscar"):
        df = search_jogadores(nome_busca, time_filtro, limite=limite)

        st.subheader("Resultados da busca")

        if df.empty:
            st.warning("Nenhum registro encontrado com os filtros informados.")
        else:
            st.write(f"Registros encontrados: **{len(df)}** (limite {limite})")
            st.dataframe(df, use_container_width=True)

            # opção para exportar
            csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar resultados em CSV",
                data=csv,
                file_name="resultado_bid.csv",
                mime="text/csv",
            )
    else:
        st.info("Use os filtros na barra lateral e clique em **Buscar** para ver os resultados.")


if __name__ == "__main__":
    main()
