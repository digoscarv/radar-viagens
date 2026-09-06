import streamlit as st
import pandas as pd
import plotly.express as px
import math
from datetime import date, timedelta
from db import (
    get_destinos_ativos, 
    get_custos_por_destino, 
    get_sazonalidade_destino,
    salvar_simulacao, 
    get_simulacoes_salvas,
    excluir_simulacao,
    get_atracoes_por_destino,
    get_roteiro_por_simulacao,
    adicionar_item_roteiro,
    excluir_item_roteiro
)
from services import get_cotacao_brl, gerar_link_google_flights

st.set_page_config(page_title="Radar de Viagens", page_icon="✈️", layout="wide")

# Helpers de formatação brasileira (1.234,56)
def fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_moeda(valor: float, moeda: str) -> str:
    val_str = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moeda} {val_str}"

NOMES_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

st.title("✈️ Radar de Viagens & Decisão")
st.caption("Central analítica para decidir para onde ir, quando ir e quanto custa.")

# 1. Carregamento dos destinos do Supabase
try:
    destinos = get_destinos_ativos()
except Exception as e:
    st.error(f"Erro de conexão com o banco de dados: {e}")
    st.stop()

if not destinos:
    st.warning("Nenhum destino ativo encontrado no banco.")
    st.stop()

mapa_destinos = {f"{d['cidade']} ({d['pais']})": d for d in destinos}

# 2. Barra Lateral de Configurações
st.sidebar.header("⚙️ Parâmetros de Decisão")

destino_selecionado_label = st.sidebar.selectbox("Destino", list(mapa_destinos.keys()))
destino = mapa_destinos[destino_selecionado_label]

qtd_pessoas = st.sidebar.number_input("Viajantes", min_value=1, max_value=10, value=2)

# FLAG DE HOSPEDAGEM GRATUITA
hospedagem_gratuita = st.sidebar.checkbox(
    "🏠 Hospedagem Gratuita", 
    value=False, 
    help="Marque se você tem casa de amigos/família ou hospedagem já paga no destino (zera o custo de hotel)."
)

duracao_dias = st.sidebar.number_input("Duração Prevista (dias)", min_value=3, max_value=60, value=10)

perfil = st.sidebar.select_slider(
    "Padrão de Conforto",
    options=["economico", "moderado", "conforto"],
    value="moderado"
)

aeroporto_origem = st.sidebar.text_input("Aeroporto Origem (IATA)", value="GRU").upper()

# 3. Processamento dos Custos Diários Base
moeda = destino["moeda"]
cotacao = get_cotacao_brl(moeda)
custos_base = get_custos_por_destino(destino["id"], perfil)

num_quartos = math.ceil(qtd_pessoas / 2)
hosp_diaria_base = custos_base.get("hospedagem", 120.0)

# Aplicação da flag de hospedagem gratuita
if hospedagem_gratuita:
    hosp_diaria_total = 0.0
else:
    hosp_diaria_total = hosp_diaria_base * num_quartos

alim_diaria_por_pessoa = custos_base.get("alimentacao", 80.0) / 2.0
lazer_diaria_por_pessoa = custos_base.get("transporte_lazer", 40.0) / 2.0

alim_diaria_total = alim_diaria_por_pessoa * qtd_pessoas
lazer_diaria_total = lazer_diaria_por_pessoa * qtd_pessoas

custo_diario_total_moeda = hosp_diaria_total + alim_diaria_total + lazer_diaria_total
custo_diario_total_brl = custo_diario_total_moeda * cotacao

# 4. Organização em Abas
tab_quando_ir, tab_simulador, tab_salvas, tab_roteiros = st.tabs([
    "🗓️ Quando Ir? (Panorama Anual)",
    "🧮 Simulador de Orçamento", 
    "📊 Viagens Salvas & Roteiro", 
    "🗺️ Dicas & Roteiros do Destino"
])

# =======================================================
# ABA 1: PANORAMA ANUAL (QUANDO IR?)
# =======================================================
with tab_quando_ir:
    st.subheader(f"🗓️ Matriz Anual de Decisão: {destino['cidade']} ({duracao_dias} dias para {qtd_pessoas} {'pessoa' if qtd_pessoas == 1 else 'pessoas'})")
    if hospedagem_gratuita:
        st.success("✅ **Flag Ativa:** Hospedagem gratuita considerada (custo de hotel zerado nos 12 meses).")

    dados_sazonalidade = get_sazonalidade_destino(destino["id"])

    if dados_sazonalidade:
        linhas_matriz = []
        for s in dados_sazonalidade:
            m_num = s["mes"]
            m_nome = NOMES_MESES.get(m_num, f"Mês {m_num}")
            fator = float(s.get("fator_multiplicador") or 1.0)
            passagem_unit = float(s.get("passagem_media_brl") or 0.0)
            passagem_grupo = passagem_unit * qtd_pessoas

            # Terrestre mensal ajustado pelo fator sazonal (se não for hospedagem gratuita)
            if hospedagem_gratuita:
                diaria_mes_moeda = (alim_diaria_total + lazer_diaria_total)
            else:
                diaria_mes_moeda = (hosp_diaria_total * fator) + alim_diaria_total + lazer_diaria_total

            terrestre_total_brl = (diaria_mes_moeda * duracao_dias) * cotacao
            custo_total_mes_brl = passagem_grupo + terrestre_total_brl

            linhas_matriz.append({
                "Mês": m_nome,
                "Temporada": s["tipo_temporada"],
                "Temp Média (°C)": f"{s['temp_media_celsius']}°C",
                "Chuva (dias)": s["dias_chuva_media"],
                "Passagem / Pessoa": fmt_brl(passagem_unit),
                "Passagens Grupo": fmt_brl(passagem_grupo),
                "Custo Terrestre": fmt_brl(terrestre_total_brl),
                "Custo Total Viagem": fmt_brl(custo_total_mes_brl),
                "_total_brl": custo_total_mes_brl,
                "_passagem_grupo": passagem_grupo,
                "_terrestre_brl": terrestre_total_brl,
                "Dica": s.get("descricao_periodo", "")
            })

        df_anual = pd.DataFrame(linhas_matriz)

        # Identificação dos meses extremos
        mes_mais_barato = df_anual.loc[df_anual["_total_brl"].idxmin()]
        mes_mais_caro = df_anual.loc[df_anual["_total_brl"].idxmax()]
        economia = mes_mais_caro["_total_brl"] - mes_mais_barato["_total_brl"]

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Mês Mais Econômico", mes_mais_barato["Mês"], fmt_brl(mes_mais_barato["_total_brl"]))
        c_m2.metric("Mês Mais Caro (Pico)", mes_mais_caro["Mês"], fmt_brl(mes_mais_caro["_total_brl"]))
        c_m3.metric("Diferença / Economia Possível", fmt_brl(economia), "Evitando a alta temporada")

        st.divider()

        # Gráfico Comparativo Plotly
        st.write("#### 📊 Custo Total da Viagem Mês a Mês (Passagens + Estadia)")
        
        df_chart = pd.DataFrame({
            "Mês": df_anual["Mês"],
            "Custo Total (R$)": df_anual["_total_brl"],
            "Passagens (R$)": df_anual["_passagem_grupo"],
            "Estadia (R$)": df_anual["_terrestre_brl"],
            "Temporada": df_anual["Temporada"]
        })

        cores_temporada = {"BAIXA": "#2ECC71", "MEDIA": "#F39C12", "ALTA": "#E74C3C"}

        fig = px.bar(
            df_chart, 
            x="Mês", 
            y="Custo Total (R$)", 
            color="Temporada",
            color_discrete_map=cores_temporada,
            text_auto=".2s",
            title=f"Estimativa Completa para {destino['cidade']} (Passagens para {qtd_pessoas} + {duracao_dias} dias de permanência)"
        )
        fig.update_layout(yaxis_title="Orçamento Total Estimado (R$)", xaxis_title="Mês do Ano")
        st.plotly_chart(fig, use_container_width=True)

        # Tabela Detalhada
        st.write("#### 📋 Matriz Detalhada Mês a Mês")
        cols_para_exibir = [
            "Mês", "Temporada", "Temp Média (°C)", "Chuva (dias)", 
            "Passagem / Pessoa", "Passagens Grupo", "Custo Terrestre", "Custo Total Viagem", "Dica"
        ]
        st.dataframe(df_anual[cols_para_exibir], use_container_width=True, hide_index=True)

    else:
        st.info(
            f"ℹ️ Os dados históricos detalhados dos 12 meses para **{destino['cidade']}** ainda não foram cadastrados na tabela de sazonalidade.\n\n"
            f"Atualmente, **Londres** já possui todos os 12 meses parametrizados no banco. "
            f"Você pode selecionar Londres acima para testar ou cadastrar os meses deste destino via SQL!"
        )

# =======================================================
# ABA 2: SIMULADOR DE ORÇAMENTO (DATA FIXA)
# =======================================================
with tab_simulador:
    st.subheader(f"🧮 Simulador para {destino['cidade']}")
    data_inicio = st.date_input("Previsão da Viagem (Data de Ida)", value=date.today() + timedelta(days=90))

    total_viagem_moeda = custo_diario_total_moeda * duracao_dias
    total_viagem_brl = total_viagem_moeda * cotacao

    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Câmbio Atual", fmt_brl(cotacao), f"1 {moeda}")
    col2.metric(f"Diária Grupo ({moeda})", fmt_moeda(custo_diario_total_moeda, moeda))
    col3.metric("Diária Grupo (BRL)", fmt_brl(custo_diario_total_brl))
    col4.metric("Custo Total Terrestre", fmt_brl(total_viagem_brl))

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.write("#### 📋 Detalhamento dos Custos Diários")
        label_quartos = "quarto" if num_quartos == 1 else "quartos"
        label_pess = "pessoa" if qtd_pessoas == 1 else "pessoas"

        cat_hosp = "Hospedagem (GRATUITA)" if hospedagem_gratuita else f"Hospedagem ({num_quartos} {label_quartos})"

        df_custos = pd.DataFrame({
            "Categoria": [
                cat_hosp, 
                f"Alimentação ({qtd_pessoas} {label_pess})", 
                f"Transporte & Lazer ({qtd_pessoas} {label_pess})"
            ],
            f"Diária ({moeda})": [
                fmt_moeda(hosp_diaria_total, moeda),
                fmt_moeda(alim_diaria_total, moeda),
                fmt_moeda(lazer_diaria_total, moeda)
            ],
            "Diária (R$)": [
                fmt_brl(hosp_diaria_total * cotacao),
                fmt_brl(alim_diaria_total * cotacao),
                fmt_brl(lazer_diaria_total * cotacao)
            ],
            f"Total {duracao_dias}d (R$)": [
                fmt_brl(hosp_diaria_total * duracao_dias * cotacao),
                fmt_brl(alim_diaria_total * duracao_dias * cotacao),
                fmt_brl(lazer_diaria_total * duracao_dias * cotacao)
            ]
        })
        st.dataframe(df_custos, use_container_width=True, hide_index=True)

    with col_right:
        st.write("#### 🛫 Monitor de Passagens (Google Flights)")
        st.info(
            f"Origem: **{aeroporto_origem}** ➔ Destino: **{destino['iata_aeroporto']}**\n\n"
            f"Período: **{data_inicio.strftime('%d/%m/%Y')}** a "
            f"**{(data_inicio + timedelta(days=duracao_dias)).strftime('%d/%m/%Y')}** ({duracao_dias} dias)\n\n"
            f"Viajantes: **{qtd_pessoas}**"
        )
        link_voos = gerar_link_google_flights(aeroporto_origem, destino["iata_aeroporto"], data_inicio, duracao_dias)
        st.link_button("🔍 Consultar Voos em Tempo Real", link_voos, type="primary")

    st.divider()

    # Formulário para Salvar
    st.write("#### 💾 Salvar esta Opção de Viagem")
    col_sim1, col_sim2 = st.columns(2)

    with col_sim1:
        sufixo_hosp = " (Hospedagem Grátis)" if hospedagem_gratuita else ""
        titulo = st.text_input("Título da Viagem", value=f"{destino['cidade']}{sufixo_hosp} - {data_inicio.year}")
        notas = st.text_area("Anotações e Ideias", placeholder="Ex: Ficar na casa da família, priorizar passeios a pé...")

    with col_sim2:
        autor_input = st.text_input("Quem está salvando?", placeholder="Digite seu nome (ex: Rodrigo, Noiva...)")
        st.write("")
        st.write("")
        if st.button("Gravar Simulação", use_container_width=True):
            nome_autor = autor_input.strip() if autor_input.strip() else "Anônimo"
            payload = {
                "destino_id": destino["id"],
                "titulo_viagem": titulo,
                "data_prevista_inicio": data_inicio.isoformat(),
                "duracao_dias": duracao_dias,
                "perfil_escolhido": perfil,
                "cotacao_moeda_brl": cotacao,
                "total_estimado_moeda_local": total_viagem_moeda,
                "total_estimado_brl": total_viagem_brl,
                "link_google_flights": link_voos,
                "notas": notas,
                "autor": nome_autor
            }
            if salvar_simulacao(payload):
                st.success("✅ Viagem gravada com sucesso! Veja o card na aba 'Viagens Salvas'.")
                st.rerun()
            else:
                st.error("Erro ao tentar salvar no banco.")

# =======================================================
# ABA 3: DASHBOARD DE VIAGENS SALVAS & ROTEIRO
# =======================================================
with tab_salvas:
    st.subheader("📊 Comparador de Viagens Salvas & Roteiro")
    simulacoes = get_simulacoes_salvas()

    if not simulacoes:
        st.info("Nenhuma viagem salva ainda. Vá até o Simulador e salve a sua primeira opção!")
    else:
        total_salvas = len(simulacoes)
        media_orcamento = sum(float(s["total_estimado_brl"]) for s in simulacoes) / total_salvas
        
        m1, m2 = st.columns(2)
        m1.metric("Total de Viagens Salvas", total_salvas)
        m2.metric("Média de Orçamento", fmt_brl(media_orcamento))

        st.write("")

        for s in simulacoes:
            sim_id = s["id"]
            dest_info = s.get("destinos", {}) or {}
            cidade = dest_info.get("cidade", "Destino")
            pais = dest_info.get("pais", "")
            moeda_s = dest_info.get("moeda", "USD")

            data_criacao_raw = s.get("created_at")
            if data_criacao_raw:
                try:
                    dt = pd.to_datetime(data_criacao_raw).tz_convert("America/Sao_Paulo")
                    data_criacao_fmt = dt.strftime("%d/%m/%Y às %H:%M")
                except Exception:
                    data_criacao_fmt = str(data_criacao_raw)[:10]
            else:
                data_criacao_fmt = "Não informada"

            titulo_card = f"📍 {s['titulo_viagem']} — {cidade}, {pais} | {fmt_brl(float(s['total_estimado_brl']))}"

            with st.expander(titulo_card, expanded=False):
                c_a, c_b, c_c = st.columns(3)
                c_a.write(f"**Duração:** {s['duracao_dias']} dias")
                c_a.write(f"**Padrão:** {s['perfil_escolhido'].capitalize()}")
                
                c_b.write(f"**Total ({moeda_s}):** {fmt_moeda(float(s['total_estimado_moeda_local']), moeda_s)}")
                c_b.write(f"**Cotação:** {fmt_brl(float(s['cotacao_moeda_brl']))}")
                
                c_c.write(f"**Salvo por:** {s.get('autor', 'Não informado')}")
                c_c.write(f"**Salvo em:** {data_criacao_fmt}")
                c_c.write(f"**Previsão:** {s['data_prevista_inicio']}")

                if s.get("notas"):
                    st.caption(f"📝 **Anotações:** {s['notas']}")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if s.get("link_google_flights"):
                        st.link_button("✈️ Reabrir Pesquisa de Voos", s["link_google_flights"])
                with col_btn2:
                    if st.button("🗑️ Excluir Viagem", key=f"del_sim_{sim_id}", type="secondary"):
                        if excluir_simulacao(sim_id):
                            st.success("Viagem excluída!")
                            st.rerun()

                st.divider()

                # ROTEIRO DIA A DIA
                st.markdown("#### 🗺️ Roteiro por Dia & Período")
                itens_roteiro = get_roteiro_por_simulacao(sim_id)

                if itens_roteiro:
                    df_rot = pd.DataFrame(itens_roteiro)
                    dias_com_atividade = sorted(df_rot["dia"].unique())

                    for d in dias_com_atividade:
                        st.markdown(f"**🗓️ Dia {d}**")
                        itens_do_dia = df_rot[df_rot["dia"] == d]
                        
                        for _, item in itens_do_dia.iterrows():
                            c_p, c_at, c_lixo = st.columns()
                            c_p.markdown(f"**{item['periodo']}**")
                            c_at.write(f"{item['atividade']} *(por {item.get('autor') or 'Anônimo'})*")
                            if c_lixo.button("❌", key=f"del_item_{item['id']}", help="Remover atividade"):
                                if excluir_item_roteiro(item["id"]):
                                    st.rerun()
                else:
                    st.info("Nenhuma atividade cadastrada no roteiro ainda.")

                st.write("")
                with st.container():
                    st.markdown("**➕ Adicionar Atividade ao Roteiro:**")
                    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                    
                    dia_escolhido = r_col1.selectbox("Dia", options=list(range(1, s["duracao_dias"] + 1)), key=f"dia_{sim_id}")
                    periodo_escolhido = r_col2.selectbox("Período", ["Manhã", "Tarde", "Noite"], key=f"per_{sim_id}")
                    atividade_texto = r_col3.text_input("Sugestão de Atividade", placeholder="Ex: Café no centro e museu", key=f"ativ_{sim_id}")
                    autor_roteiro = r_col4.text_input("Autor", value=s.get("autor", "Rodrigo"), key=f"aut_{sim_id}")

                    if st.button("Adicionar ao Roteiro", key=f"btn_add_rot_{sim_id}"):
                        if atividade_texto.strip():
                            novo_item = {
                                "simulacao_id": sim_id,
                                "dia": dia_escolhido,
                                "periodo": periodo_escolhido,
                                "atividade": atividade_texto.strip(),
                                "autor": autor_roteiro.strip() if autor_roteiro.strip() else "Anônimo"
                            }
                            if adicionar_item_roteiro(novo_item):
                                st.success("Atividade adicionada!")
                                st.rerun()
                        else:
                            st.warning("Digite uma atividade antes de salvar.")

# =======================================================
# ABA 4: DICAS & ROTEIROS DO DESTINO
# =======================================================
with tab_roteiros:
    st.subheader(f"🗺️ Pontos de Interesse & Dicas para {destino['cidade']}")
    atracoes = get_atracoes_por_destino(destino["id"])

    if not atracoes:
        st.info(f"Ainda não há atrações cadastradas para {destino['cidade']} no banco de dados.")
    else:
        for atracao in atracoes:
            with st.container():
                st.markdown(f"### {atracao['nome']} `[{atracao['categoria']}]`")
                c1, c2 = st.columns(2)
                
                custo = float(atracao["custo_moeda_local"])
                c1.write(f"🎟️ **Ingresso:** {'Gratuito' if custo == 0 else fmt_moeda(custo, destino['moeda'])}")
                c1.write(f"⏰ **Horário:** {atracao.get('horario_funcionamento', 'Consulte no local')}")
                
                c2.write(f"💡 **Dica Prática:** {atracao.get('dicas', 'Sem observações.')}")
                st.divider()