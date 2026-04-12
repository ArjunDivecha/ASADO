"""
ASADO - Country Research Dashboard
===================================
Interactive Streamlit frontend for the ASADO country data platform.
Reads directly from DuckDB + Neo4j via the existing AsadoDB bridge.

Usage:
    streamlit run frontend/app.py

Runs at http://localhost:8501
"""

import sys
import os
from pathlib import Path

import duckdb
import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pyvis.network import Network
from scipy.spatial.distance import cosine as cosine_dist
import streamlit as st

# Project root on sys.path so we can import scripts.db_bridge
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Constants
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"
TRADE_PQ = BASE_DIR / "Data" / "processed" / "bilateral_trade_matrix.parquet"
BANK_PQ = BASE_DIR / "Data" / "processed" / "bilateral_banking_matrix.parquet"

COUNTRY_REGION = {
    "Australia": "Asia-Pacific", "Brazil": "Latin America",
    "Canada": "North America", "Chile": "Latin America",
    "ChinaA": "Asia-Pacific", "ChinaH": "Asia-Pacific",
    "Denmark": "Europe", "France": "Europe", "Germany": "Europe",
    "Hong Kong": "Asia-Pacific", "India": "Asia-Pacific",
    "Indonesia": "Asia-Pacific", "Italy": "Europe", "Japan": "Asia-Pacific",
    "Korea": "Asia-Pacific", "Malaysia": "Asia-Pacific", "Mexico": "Latin America",
    "NASDAQ": "North America", "Netherlands": "Europe",
    "Philippines": "Asia-Pacific", "Poland": "Europe",
    "Saudi Arabia": "Middle East", "Singapore": "Asia-Pacific",
    "South Africa": "Africa", "Spain": "Europe", "Sweden": "Europe",
    "Switzerland": "Europe", "Taiwan": "Asia-Pacific", "Thailand": "Asia-Pacific",
    "Turkey": "Europe", "U.K.": "Europe", "U.S.": "North America",
    "US SmallCap": "North America", "Vietnam": "Asia-Pacific",
}

REGION_COLORS = {
    "Asia-Pacific": "#3B82F6", "Europe": "#10B981", "Latin America": "#F59E0B",
    "North America": "#8B5CF6", "Middle East": "#EF4444", "Africa": "#F97316",
}

# Custom CSS
st.set_page_config(
    page_title="ASADO Research",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; color: #9CA3AF; }
    div[data-testid="stCodeBlock"] code {
        font-family: 'SF Mono', 'JetBrains Mono', monospace;
    }
    .reportview-container .main .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# Cached Data Loaders

@st.cache_data(ttl=3600)
def get_countries():
    if not DB_PATH.exists():
        return []
    con = duckdb.connect(str(DB_PATH), read_only=True)
    countries = con.execute(
        "SELECT DISTINCT country FROM unified_panel ORDER BY country"
    ).fetchdf()["country"].tolist()
    con.close()
    return countries

@st.cache_data(ttl=3600)
def get_unified_panel_summary():
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("""
        SELECT variable, source,
               COUNT(DISTINCT country) AS n_countries,
               COUNT(*) AS n_obs,
               MIN(date) AS first_date,
               MAX(date) AS last_date
        FROM unified_panel
        GROUP BY variable, source
        ORDER BY variable
    """).fetchdf()
    con.close()
    return df

@st.cache_data(ttl=3600)
def get_trade_matrix():
    if not TRADE_PQ.exists():
        return pd.DataFrame()
    return pd.read_parquet(TRADE_PQ)

@st.cache_data(ttl=3600)
def get_banking_matrix():
    if not BANK_PQ.exists():
        return pd.DataFrame()
    return pd.read_parquet(BANK_PQ)

@st.cache_data(ttl=3600)
def get_latest_factors():
    from scripts.db_bridge import AsadoDB
    with AsadoDB() as db:
        return db.query_panel("""
            WITH ranked AS (
                SELECT country, variable, value, date,
                       ROW_NUMBER() OVER (PARTITION BY country, variable ORDER BY date DESC)
                           AS rn
                FROM unified_panel
                WHERE value IS NOT NULL
            )
            SELECT country, variable, value, date FROM ranked WHERE rn = 1
        """)

@st.cache_resource
def get_db():
    from scripts.db_bridge import AsadoDB
    return AsadoDB()

# Utility Functions

def _safe_float(val, decimals=1):
    """Safely format a float value."""
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None

@st.cache_data(ttl=3600)
def get_country_meta():
    """Get country name -> iso3, dm_em, region mapping from Neo4j."""
    try:
        db = get_db()
        records = db.query_graph(
            "MATCH (c:Country) "
            "RETURN c.t2_name AS name, c.iso3 AS iso3, "
            "c.dm_em AS dm_em, c.region AS region"
        )
        name_to_iso3 = {r["name"]: r["iso3"] for r in records}
        iso3_to_name = {r["iso3"]: r["name"] for r in records}
        iso3_to_region = {r["iso3"]: r["region"] for r in records}
        iso3_to_dm = {r["iso3"]: r["dm_em"] for r in records}
        return name_to_iso3, iso3_to_name, iso3_to_region, iso3_to_dm
    except Exception:
        return {}, {}, {}, {}

def build_pyvis_network(nodes_df, edges_df, directed=True):
    """Build a Pyvis interactive network graph and return HTML."""
    G = nx.DiGraph() if directed else nx.Graph()

    for _, row in nodes_df.iterrows():
        nid = str(row["id"])
        G.add_node(
            nid,
            label=str(row.get("label", nid)),
            size=float(row.get("size", 10)),
            color=row.get("color", "#3B82F6"),
            title=f"{row.get('label', nid)}",
        )

    for _, row in edges_df.iterrows():
        src = str(row["source"])
        tgt = str(row["target"])
        w = float(row.get("width", 1))
        label = str(row.get("label", ""))
        G.add_edge(
            src, tgt,
            value=max(w, 0.5),
            title=label,
            color="rgba(156,163,175,0.4)",
        )

    nt = Network(
        height="600px", width="100%", notebook=True,
        directed=directed, bgcolor="#0E1117", font_color="#E5E7EB",
    )
    nt.from_nx(G)
    nt.toggle_physics(True)
    nt.set_options("""{
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.01,
          "springLength": 120,
          "springConstant": 0.05
        },
        "solver": "forceAtlas2Based",
        "minVelocity": 0.75,
        "maxVelocity": 30
      },
      "nodes": {
        "borderWidth": 1,
        "borderWidthSelected": 3,
        "shadow": {
          "enabled": true,
          "color": "rgba(59,130,246,0.3)",
          "size": 10
        }
      },
      "edges": { "smooth": { "type": "continuous" } }
    }""")

    html = nt.generate_html()
    html = html.replace(
        "</head>",
        "<style>body,div,span,table,td{background:#0E1117!important;"
        "color:#E5E7EB!important;}</style></head>",
    )
    return html

# Sidebar

countries = get_countries()
if not countries:
    st.error("Database not found. Run `python scripts/setup_duckdb.py` first.")
    st.stop()

name_to_iso3, iso3_to_name, iso3_to_region, iso3_to_dm = get_country_meta()

with st.sidebar:
    st.markdown("### ASADO Research")
    st.markdown("---")
    st.caption("34-country T2 Master Universe")
    if DB_PATH.exists():
        st.caption(f"DuckDB: {os.path.getsize(DB_PATH) / 1e6:.1f} MB")
    st.markdown("---")
    selected_country = st.selectbox("Country", ["All Countries"] + countries, index=0)

# Main Navigation

tab_dashboard, tab_trade, tab_banking, tab_similarity, tab_factors, tab_query = st.tabs([
    "Dashboard", "Trade Network", "Banking Exposure", "Similarity",
    "Factor Explorer", "Free Query",
])

# =================================================================
# TAB 1 - Country Overview Dashboard
# =================================================================

with tab_dashboard:
    st.markdown("### Country Overview")

    country = selected_country if selected_country != "All Countries" else None

    if country:
        factors_all = get_latest_factors()
        c_fac = factors_all[factors_all["country"] == country]
        iso3 = name_to_iso3.get(country)

        gdp_row = c_fac[c_fac["variable"] == "WB_GDP"]
        gdp_val = gdp_row["value"].iloc[0] if not gdp_row.empty else None
        gdp_growth_row = c_fac[c_fac["variable"] == "IMF_WEO_GDP_Growth"]
        gdp_growth = gdp_growth_row["value"].iloc[0] if not gdp_growth_row.empty else None
        infl_row = c_fac[c_fac["variable"].isin(["IMF_CPI_Inflation_YoY", "IMF_WEO_Inflation"])]
        infl_val = infl_row["value"].iloc[0] if not infl_row.empty else None

        db = get_db()
        c_meta = db.country_profile(country)["graph"]
        dm_em = c_meta.get("dm_em", "")
        region = c_meta.get("region", "")
        currency = c_meta.get("currency", "")

        st.markdown(f"#### {country}")
        st.markdown(f"*{dm_em} | {region} | {currency}*")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            v = _safe_float(gdp_val / 1e12, 1) if gdp_val is not None else None
            st.metric(label="GDP", value=f"{v}T" if v else "—")
        with col2:
            v = _safe_float(gdp_growth, 1) if gdp_growth is not None else None
            st.metric(label="GDP Growth", value=f"{v}%" if v else "—")
        with col3:
            v = _safe_float(infl_val, 1) if infl_val is not None else None
            st.metric(label="Inflation (YoY)", value=f"{v}%" if v else "—")
        with col4:
            trade = get_trade_matrix()
            n_partners = 0
            if not trade.empty and iso3:
                n_partners = len(
                    trade[(trade["reporter_iso3"] == iso3) &
                          (trade["total_trade_usd"] > 1e8)]
                )
            st.metric(label="Trade Partners", value=str(n_partners))

        st.markdown("#### Key Factors (Latest)")
        key_vars = [
            "WB_GDP", "IMF_WEO_GDP_Growth", "IMF_WEO_Inflation",
            "IMF_WEO_Debt_GDP", "IMF_WEO_Unemployment", "BIS_Credit_GDP_Gap",
            "BIS_REER", "BIS_Policy_Rate", "EPU", "GPR",
        ]
        shown = []
        for var in key_vars:
            row_data = c_fac[c_fac["variable"] == var]
            if not row_data.empty:
                shown.append({
                    "Factor": var,
                    "Value": _safe_float(row_data["value"].iloc[0], 2),
                    "Date": pd.Timestamp(row_data["date"].iloc[0]).strftime("%Y-%m-%d"),
                })
        if shown:
            st.dataframe(
                pd.DataFrame(shown),
                use_container_width=True,
                height=300,
                hide_index=True,
            )
        st.markdown(f"**{len(c_fac)} variables** available for {country}")

    else:
        st.markdown("#### All 34 Countries at a Glance")
        factors_all = get_latest_factors()
        summary_rows = []
        for c in countries:
            c_fac = factors_all[factors_all["country"] == c]
            row = {"Country": c, "Region": COUNTRY_REGION.get(c, "")}
            for var in ["WB_GDP", "IMF_WEO_GDP_Growth", "IMF_WEO_Inflation", "EPU", "BIS_Credit_GDP_Gap"]:
                val = c_fac[c_fac["variable"] == var]["value"]
                if not val.empty:
                    row[var] = _safe_float(val.iloc[0], 2)
            summary_rows.append(row)
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, height=500)

        st.markdown("##### Variables Available per Country")
        coverage = factors_all.groupby("country").agg(
            n_vars=("variable", "nunique"),
            last_date=("date", "max"),
        ).reset_index()
        coverage["Country"] = coverage["country"].apply(
            lambda x: f"{x} ({COUNTRY_REGION.get(x, '')})"
        )
        coverage = coverage[["Country", "n_vars", "last_date"]].rename(
            columns={"n_vars": "Variables", "last_date": "Latest Date"}
        )
        coverage = coverage.sort_values("Variables", ascending=False)
        st.dataframe(coverage, use_container_width=True, height=400)

# =================================================================
# TAB 2 - Trade Network
# =================================================================

with tab_trade:
    st.markdown("### Bilateral Trade Network")
    st.caption("IMF Direction of Trade Statistics - latest year, pairs > $100M")

    trade = get_trade_matrix()
    if trade.empty:
        st.warning("No trade data. Run: `python scripts/collect_bilateral.py --trade-only`")
    else:
        year = int(trade["year"].iloc[0])
        st.markdown(f"**Data Year: {year}**")

        if selected_country != "All Countries" and selected_country in name_to_iso3:
            sel_iso = name_to_iso3[selected_country]
            trade_c = trade[trade["reporter_iso3"] == sel_iso].sort_values(
                "total_trade_usd", ascending=False
            )
        else:
            trade_c = trade.sort_values("total_trade_usd", ascending=False)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_exp = trade_c["exports_usd"].sum() / 1e12
            st.metric("Total Exports", f"{_safe_float(total_exp, 1)}T" if total_exp else "—")
        with col2:
            total_imp = trade_c["imports_usd"].sum() / 1e12
            st.metric("Total Imports", f"{_safe_float(total_imp, 1)}T" if total_imp else "—")
        with col3:
            st.metric("Trade Partners", len(trade_c))
        with col4:
            if not trade_c.empty:
                top_idx = trade_c["total_trade_usd"].idxmax()
                top_iso = trade_c.loc[top_idx, "counterpart_iso3"]
                top_name = iso3_to_name.get(top_iso, top_iso)
                top_val = _safe_float(trade_c.loc[top_idx, "total_trade_usd"] / 1e9, 0)
                st.metric("Largest Partner", f"${top_val}B", delta=top_name)

        top10 = trade_c.head(10).copy()
        top10["Counterpart"] = top10["counterpart_iso3"].map(iso3_to_name)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top10["Counterpart"],
            y=top10["exports_usd"] / 1e9,
            name="Exports",
            marker_color="#10B981",
        ))
        fig.add_trace(go.Bar(
            x=top10["Counterpart"],
            y=top10["imports_usd"] / 1e9,
            name="Imports",
            marker_color="#3B82F6",
        ))
        fig.update_layout(
            title="Top 10 Trade Partners (USD Billions)",
            barmode="group", height=400,
            margin=dict(t=40, b=40, l=40, r=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E5E7EB", size=10),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                font=dict(color="#E5E7EB"),
            ),
            xaxis=dict(tickangle=45, gridcolor="#1f2937", tickfont=dict(color="#9CA3AF")),
            yaxis=dict(gridcolor="#1f2937", tickfont=dict(color="#9CA3AF")),
        )
        st.plotly_chart(fig, use_container_width=True)

        if selected_country == "All Countries":
            st.markdown("#### Global Trade Network")
            top_network = trade.groupby("reporter_iso3").apply(
                lambda g: g.nlargest(8, "total_trade_usd")
            ).reset_index(drop=True)

            nd = []
            seen = set()
            for _, r in top_network.iterrows():
                for iso in [r["reporter_iso3"], r["counterpart_iso3"]]:
                    if iso not in seen:
                        seen.add(iso)
                        vol = top_network[top_network["reporter_iso3"] == iso]["total_trade_usd"].sum()
                        size = max(np.sqrt(vol / 1e9) * 5, 8)
                        color = REGION_COLORS.get(iso3_to_region.get(iso, ""), "#6B7280")
                        nd.append({
                            "id": iso,
                            "label": iso3_to_name.get(iso, iso),
                            "size": size, "color": color,
                        })

            ed = []
            for _, r in top_network.iterrows():
                ed.append({
                    "source": r["reporter_iso3"],
                    "target": r["counterpart_iso3"],
                    "width": max(np.log10(r["total_trade_usd"] + 1) * 2, 1),
                    "label": f"${r['total_trade_usd'] / 1e9:.1f}B",
                })

            html = build_pyvis_network(
                pd.DataFrame(nd), pd.DataFrame(ed), directed=True,
            )
            st.components.v1.html(html, height=650, scrolling=True)
        else:
            st.markdown(f"#### {selected_country} - Top Trade Partners")
            tt = top10.copy()
            tt["Exports ($B)"] = tt["exports_usd"] / 1e9
            tt["Imports ($B)"] = tt["imports_usd"] / 1e9
            tt["Total ($B)"] = tt["total_trade_usd"] / 1e9
            tt = tt[["Counterpart", "Exports ($B)", "Imports ($B)", "Total ($B)", "trade_share_pct"]]
            tt.columns = ["Counterpart", "Exports ($B)", "Imports ($B)", "Total ($B)", "Share (%)"]
            st.dataframe(tt, use_container_width=True, hide_index=True, height=400)

# =================================================================
# TAB 3 - Banking Exposure
# =================================================================

with tab_banking:
    st.markdown("### Cross-Border Banking Exposure")
    st.caption("BIS Locational Banking Statistics - latest quarter")

    banking = get_banking_matrix()
    if banking.empty:
        st.warning("No banking data. Run: `python scripts/collect_bilateral.py --bank-only`")
    else:
        quarter = str(banking["quarter"].iloc[0])
        st.markdown(f"**Data Quarter: {quarter}**")

        if selected_country != "All Countries" and selected_country in name_to_iso3:
            sel_iso = name_to_iso3[selected_country]
            bank_c = banking[banking["reporter_iso3"] == sel_iso].sort_values(
                "claims_usd_millions", ascending=False
            )
        else:
            bank_c = banking.sort_values("claims_usd_millions", ascending=False)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_claims = bank_c["claims_usd_millions"].sum()
            st.metric("Total Claims ($M)", f"{_safe_float(total_claims, 0):,}")
        with col2:
            st.metric("Counterparties", len(bank_c))
        with col3:
            if not bank_c.empty:
                top_iso = bank_c.loc[
                    bank_c["claims_usd_millions"].idxmax(), "counterpart_iso3"
                ]
                top_pct = bank_c["share_of_total_claims_pct"].max()
                top_name = iso3_to_name.get(top_iso, top_iso)
                st.metric(
                    "Largest Exposure",
                    f"{_safe_float(top_pct, 1)}%",
                    delta=top_name,
                )
        with col4:
            if len(bank_c) > 0:
                shares = bank_c["share_of_total_claims_pct"] / 100
                hhi = (shares ** 2).sum()
                st.metric("HHI Concentration", f"{_safe_float(hhi, 3)}")

        top15 = bank_c.head(15).copy()
        top15["Counterparty"] = top15["counterpart_iso3"].map(iso3_to_name)
        top15["Claims_T"] = top15["claims_usd_millions"] / 1e6

        fig_b = go.Figure()
        fig_b.add_trace(go.Bar(
            x=top15["Counterparty"],
            y=top15["Claims_T"],
            marker=dict(
                color=top15["claims_usd_millions"],
                colorscale="Blues",
            ),
        ))
        fig_b.update_layout(
            title="Top 15 Banking Exposures (USD Trillions)",
            height=400,
            margin=dict(t=40, b=40, l=40, r=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E5E7EB", size=10),
            xaxis=dict(tickangle=45, gridcolor="#1f2937", tickfont=dict(color="#9CA3AF")),
            yaxis=dict(
                title="Claims ($T)",
                gridcolor="#1f2937",
                tickfont=dict(color="#9CA3AF"),
            ),
        )
        st.plotly_chart(fig_b, use_container_width=True)

        if selected_country == "All Countries":
            st.markdown("#### Global Banking Network")
            top_bank = banking.groupby("reporter_iso3").apply(
                lambda g: g.nlargest(6, "claims_usd_millions")
            ).reset_index(drop=True)

            nd = []
            seen = set()
            for _, r in top_bank.iterrows():
                for iso in [r["reporter_iso3"], r["counterpart_iso3"]]:
                    if iso not in seen:
                        seen.add(iso)
                        total = top_bank[top_bank["reporter_iso3"] == iso]["claims_usd_millions"].sum()
                        size = max(np.log10(total + 1) * 3, 8)
                        color = REGION_COLORS.get(iso3_to_region.get(iso, ""), "#6B7280")
                        nd.append({
                            "id": iso,
                            "label": iso3_to_name.get(iso, iso),
                            "size": size, "color": color,
                        })

            ed = []
            for _, r in top_bank.iterrows():
                ed.append({
                    "source": r["reporter_iso3"],
                    "target": r["counterpart_iso3"],
                    "width": max(np.log10(r["claims_usd_millions"] + 1) * 2, 1),
                    "label": f"${r['claims_usd_millions'] / 1e3:.0f}B",
                })

            html = build_pyvis_network(
                pd.DataFrame(nd), pd.DataFrame(ed), directed=True,
            )
            st.components.v1.html(html, height=650, scrolling=True)
        else:
            st.markdown(f"#### {selected_country} - Banking Exposures")
            bt = top15[["Counterparty", "Claims_T", "share_of_total_claims_pct"]].copy()
            bt.columns = ["Counterparty", "Claims ($T)", "Share (%)"]
            st.dataframe(bt, use_container_width=True, hide_index=True, height=500)

# =================================================================
# TAB 4 - Similarity (Vector Search)
# =================================================================

with tab_similarity:
    st.markdown("### Country Similarity Search")
    st.caption("PCA-compressed factor-state vectors - cosine similarity")

    try:
        db = get_db()
        emb_records = db.query_graph(
            "MATCH (c:Country) WHERE c.state_embedding IS NOT NULL "
            "RETURN c.t2_name AS name, c.iso3 AS iso3, c.dm_em AS dem, "
            "c.region AS region, c.embedding_date AS date, "
            "c.state_embedding AS embedding"
        )
    except Exception:
        emb_records = []

    if not emb_records:
        st.warning("No embeddings found. Run `python scripts/build_embeddings.py`")
    else:
        emb_countries = sorted([r.get("c.name", r.get("country", r.get("name", ""))) for r in emb_records if any(k in r for k in ["c.name", "country", "name"])])
        emb_countries = [c for c in emb_countries if c]
        sim_country = st.selectbox(
            "Pick a country to find similar ones:", emb_countries,
        )

        if sim_country:
            results = db.query_graph(
                "MATCH (c:Country {t2_name: $name}) "
                "WHERE c.state_embedding IS NOT NULL "
                "CALL db.index.vector.queryNodes('countryStateIndex', 6, c.state_embedding) "
                "YIELD node, score "
                "WHERE node <> c AND node.t2_name IS NOT NULL "
                "RETURN node.t2_name AS country, node.dm_em AS dm_em, "
                "node.region AS region, round(score * 1000) / 1000.0 AS score "
                "ORDER BY score DESC",
                name=sim_country,
            )

            if results:
                col_a, col_b = st.columns([2, 1])

                with col_a:
                    st.markdown(f"**Most similar to {sim_country}:**")

                    # Normalize keys: Neo4j returns aliases like 'node.t2_name' or just 'country'
                    # Try both key styles
                    def _get(r, *keys):
                        for k in keys:
                            if k in r:
                                return r[k]
                        # Try compound keys like 'node.country'
                        for k in keys:
                            for actual_key in r:
                                if actual_key.endswith('.' + k):
                                    return r[actual_key]
                        return None

                    sim_rows = []
                    for r in results:
                        country = _get(r, "country", "node.country", "node.t2_name")
                        dm_em = _get(r, "dm_em", "node.dm_em", "node.dem")
                        region = _get(r, "region", "node.region")
                        score = _get(r, "score")
                        if country is not None:
                            sim_rows.append({
                                "Country": str(country),
                                "DM/EM": str(dm_em) if dm_em else "",
                                "Region": str(region) if region else "",
                                "Score": round(float(score), 3) if score else 0,
                            })
                    sim_df = pd.DataFrame(sim_rows)
                    st.dataframe(sim_df, use_container_width=True, hide_index=True, height=220)

                with col_b:
                    if not sim_df.empty:
                        fig_s = go.Figure()
                        fig_s.add_trace(go.Bar(
                            y=sim_df["Country"],
                            x=sim_df["Score"],
                            orientation="h",
                            marker=dict(
                                color=sim_df["Score"],
                                colorscale=[[0, "#1E3A5F"], [1, "#3B82F6"]],
                                colorbar=dict(tickfont=dict(color="#9CA3AF"), title="Score"),
                            ),
                            text=[f"{s:.3f}" for s in sim_df["Score"]],
                            textposition="outside",
                            textfont=dict(color="#E5E7EB", size=10),
                        ))
                        fig_s.update_layout(
                            title="Similarity Scores",
                            height=400,
                            margin=dict(t=40, b=40, l=80, r=20),
                            showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#E5E7EB", size=10),
                            xaxis=dict(
                                gridcolor="#1f2937",
                                tickfont=dict(color="#9CA3AF"),
                                range=[0, sim_df["Score"].max() + 0.05]
                            ),
                            yaxis=dict(
                                gridcolor="#1f2937",
                                tickfont=dict(color="#E5E7EB")
                            ),
                        )
                        st.plotly_chart(fig_s, use_container_width=True)

                st.markdown("#### Pairwise Similarity Matrix")
                st.caption("Cosine similarity across all 34 countries")

                embeddings = {}
                for r in emb_records:
                    name = r["c.name"]
                    vec_str = r["c.embedding"]
                    if not isinstance(vec_str, list):
                        s = str(vec_str).strip("[]")
                        embeddings[name] = [float(x.strip()) for x in s.split(",")]
                    else:
                        embeddings[name] = list(vec_str)

                country_names = sorted(embeddings.keys())
                n = len(country_names)
                sim_matrix = np.zeros((n, n))
                for i in range(n):
                    for j in range(n):
                        if i == j:
                            sim_matrix[i, j] = 1.0
                        else:
                            sim_matrix[i, j] = 1 - cosine_dist(
                                embeddings[country_names[i]],
                                embeddings[country_names[j]],
                            )

                fig_heat = px.imshow(
                    sim_matrix,
                    x=country_names,
                    y=country_names,
                    color_continuous_scale="Blues",
                    zmin=0.2,
                    zmax=1.0,
                )
                fig_heat.update_layout(
                    height=700,
                    margin=dict(l=120, b=120, t=40, r=20),
                    xaxis=dict(tickfont=dict(size=8, color="#9CA3AF"), tickangle=60),
                    yaxis=dict(tickfont=dict(size=8, color="#9CA3AF")),
                )
                st.plotly_chart(fig_heat, use_container_width=True)

# =================================================================
# TAB 5 - Factor Explorer
# =================================================================

with tab_factors:
    st.markdown("### Factor Explorer")
    st.caption("Cross-sectional view of any factor across all 34 countries")

    var_list = get_unified_panel_summary()
    if var_list.empty:
        st.warning("No data in DuckDB. Run setup_duckdb.py first")
    else:
        categories = sorted(var_list["source"].unique())
        cat_filter = st.multiselect("Filter by Source", ["All"] + categories, default=["All"])

        if "All" not in cat_filter:
            vars_avail = var_list[var_list["source"].isin(cat_filter)]["variable"].tolist()
        else:
            vars_avail = var_list["variable"].tolist()

        selected_var = st.selectbox("Factor Variable", vars_avail)

        latest = get_latest_factors()
        var_data = latest[latest["variable"] == selected_var].copy()

        if var_data.empty:
            st.info("No data for this variable")
        else:
            # Make sure we have country names not ISO3
            if "country" in var_data.columns:
                first_val = var_data["country"].iloc[0]
                if first_val not in iso3_to_name and len(first_val) != 3:
                    display_df = var_data[["country", "value", "date"]].copy()
                    display_df.columns = ["Country", "Value", "Date"]
                else:
                    var_data["country_name"] = var_data["country"].map(iso3_to_name)
                    display_df = var_data[["country_name", "value", "date"]].copy()
                    display_df.columns = ["Country", "Value", "Date"]
            else:
                display_df = var_data[["value", "date"]].copy()
                display_df.columns = ["Value", "Date"]
                display_df["Country"] = var_data.get("country", "Unknown")
                display_df = display_df[["Country", "Value", "Date"]]

            display_df = display_df.sort_values("Value", ascending=False)
            display_df["Date"] = pd.to_datetime(display_df["Date"]).dt.strftime("%Y-%m-%d")

            fig = px.bar(
                display_df,
                x="Country",
                y="Value",
                title=f"Cross-Sectional Ranking: {selected_var}",
                color="Value",
                color_continuous_scale="RdYlBu_r",
                labels={"Value": "Value", "Country": "Country"},
            )
            fig.update_layout(
                height=500,
                margin=dict(t=40, l=20, r=40, b=100),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E5E7EB", size=9),
                xaxis=dict(tickangle=60, gridcolor="#1f2937", tickfont=dict(color="#9CA3AF")),
                yaxis=dict(gridcolor="#1f2937", tickfont=dict(color="#9CA3AF")),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"**Sorted values for {selected_var}**")
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)

# =================================================================
# TAB 6 - Free Query Playground
# =================================================================

with tab_query:
    st.markdown("### Free Query Playground")
    st.caption("Run raw SQL (DuckDB) or Cypher (Neo4j) queries")

    templates = {
        "Top 5 Countries by GDP":
            "SELECT country, value FROM unified_panel\n"
            "WHERE variable = 'WB_GDP'\n"
            "AND date = (SELECT MAX(date) FROM unified_panel WHERE variable = 'WB_GDP')\n"
            "ORDER BY value DESC LIMIT 5",
        "GDP Growth vs Inflation":
            "SELECT country, variable, value\nFROM unified_panel\n"
            "WHERE variable IN ('IMF_WEO_GDP_Growth', 'IMF_CPI_Inflation_YoY')\n"
            "AND date >= '2020-01-01'\nORDER BY country, variable, date",
        "Crisis History":
            "MATCH (c:Country)-[:HAS_CRISIS_HISTORY]->(ce:CrisisEvent)\n"
            "RETURN c.t2_name AS country, ce.name AS crisis, ce.type AS type",
        "Similarity to Turkey":
            "MATCH (c:Country {t2_name: 'Turkey'})\n"
            "CALL db.index.vector.queryNodes('countryStateIndex', 6, c.state_embedding)\n"
            "YIELD node, score\n"
            "RETURN node.t2_name AS country, score ORDER BY score DESC",
        "All Countries + ISO":
            "MATCH (c:Country) RETURN c.t2_name AS name, c.iso3, c.dm_em, c.region\n"
            "ORDER BY c.t2_name",
        "Brazil's Top Trade Partners":
            "MATCH (c:Country {t2_name: 'Brazil'})-[t:TRADES_WITH]->(p)\n"
            "RETURN p.t2_name AS partner, t.exports_usd, t.imports_usd, t.total_trade_usd, "
            "t.trade_share_pct\nORDER BY t.total_trade_usd DESC LIMIT 10",
    }

    st.markdown("**Query Templates** (click to load):")
    cols = st.columns(3)
    for i, (name, query) in enumerate(templates.items()):
        with cols[i % 3]:
            if st.button(name, key=f"tmpl_{i}"):
                st.session_state["query_prefill"] = query

    query_engine = st.selectbox("Database", ["DuckDB (SQL)", "Neo4j (Cypher)"])
    default_query = st.session_state.get(
        "query_prefill",
        "SELECT * FROM unified_panel LIMIT 10"
    )
    query_text = st.text_area(
        "Enter Query",
        value=default_query,
        height=150,
        key="main_query",
    )

    if st.button("Run Query", type="primary"):
        try:
            db = get_db()
            if query_engine == "DuckDB (SQL)":
                result_df = db.query_panel(query_text)
                st.dataframe(result_df, use_container_width=True, height=500)
                st.info(f"{len(result_df)} rows | {len(result_df.columns)} columns")
            else:
                result = db.query_graph(query_text)
                result_df = pd.DataFrame(result)
                st.dataframe(result_df, use_container_width=True, height=500)
                st.info(f"{len(result_df)} rows | {len(result_df.columns)} columns")
        except Exception as e:
            st.error(f"Query failed: {e}")

# Footer
st.markdown("---")
st.caption("ASADO Country Research Platform | 34 T2 Master Countries | DuckDB + Neo4j | April 2026")
