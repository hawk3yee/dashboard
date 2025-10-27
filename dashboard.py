import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
import io
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from datetime import datetime

# --- Configuration & CSS ---
st.set_page_config(layout="wide", page_title="M2 MBFA Terminal", page_icon="📊", initial_sidebar_state="expanded")

# --- Constantes (Mises à jour avec les règles du mandat) ---
EXCEL_URL = "https://docs.google.com/spreadsheets/d/1VqgRMRJJ3DaCYKJ1OT77LFn9ExUUifO7x3Zzqq6fmwQ/export?format=xlsx"
MANAGEMENT_FEE_ANNUAL = 0.01 # 1%
CASH_RATE_ANNUAL = 0.015 # 1.5%
TRANSACTION_FEE_RATE = 0.001 # 0.10%
RISK_FREE_RATE_ANNUAL = 0.015 # Supposons égal au taux cash pour Sharpe
TRADING_DAYS = 252 # Pour annualisation du risque (Vol, Sharpe, TE)
CALENDAR_DAYS = 365 # Pour annualisation/journalisation des frais et taux cash
BENCHMARK_WEIGHTS = {'Action': 0.60, 'Gov bond': 0.20, 'Commodities': 0.15, 'Cash': 0.05} #
START_DATE_SIMULATION = pd.to_datetime('2025-10-06') #
INITIAL_NAV_EUR = 100_000_000 # 100M €
CASH_TICKER_NAME = "CASH EUR"

# Palette Bloomberg authentique
COLORS = {
    'bg_dark': '#0A0E27', 'bg_secondary': '#0F1630', 'bg_panel': '#141B3D',
    'accent_orange': '#fb8b1e', 'accent_yellow': '#FFB81C', 'text_primary': '#E8F0FF',
    'text_secondary': '#8B9DC3', 'success': '#4af6c3', 'danger': '#ff433d',
    'border': '#1F2A5C', 'grid': '#1A2347', 'blue_bright': '#0068ff'
}

# --- CSS Style Bloomberg ---
custom_css = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
    /* Global */
    .main {{ background-color: {COLORS['bg_dark']}; color: {COLORS['text_primary']}; }}
    .block-container {{ padding: 1.5rem 2rem; max-width: 100%; }}
    * {{ font-family: 'Inter', sans-serif; }}
    /* Headers Bloomberg Style */
    .bloomberg-header {{ background: linear-gradient(90deg, {COLORS['bg_dark']} 0%, {COLORS['bg_panel']} 50%, {COLORS['bg_dark']} 100%); padding: 1.2rem 2rem; border-left: 5px solid {COLORS['accent_orange']}; border-bottom: 2px solid {COLORS['accent_orange']}; margin-bottom: 1.5rem; box-shadow: 0 2px 20px rgba(251, 139, 30, 0.3); }}
    .bloomberg-header h1 {{ color: {COLORS['accent_orange']}; font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 2.2rem; margin: 0; letter-spacing: 0.15em; text-transform: uppercase; text-shadow: 0 0 10px rgba(251, 139, 30, 0.5); }}
    .bloomberg-header .subtitle {{ color: {COLORS['text_secondary']}; font-size: 0.85rem; margin-top: 0.5rem; letter-spacing: 0.08em; font-family: 'Roboto Mono', monospace; }}

    /* Market Ticker Bar */
    .market-ticker {{
        background: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']}; border-left: 3px solid {COLORS['success']};
        padding: 0.8rem 1rem; margin-bottom: 1.5rem; font-family: 'Roboto Mono', monospace;
        overflow: hidden; white-space: nowrap; box-sizing: border-box; position: relative;
    }}
    .ticker-label {{ color: {COLORS['text_secondary']}; font-size: 0.75rem; display: block; margin-bottom: 0.4rem; white-space: normal; }}
    .ticker-wrap {{ overflow: hidden; width: 100%; display: block; }}
    .ticker-content {{ display: inline-block; padding-left: 100%; animation: scroll-left 35s linear infinite; white-space: nowrap; }}
    .ticker-content span {{ color: #FFF; font-size: 0.85rem; vertical-align: middle; }}
    .ticker-content strong {{ vertical-align: middle; }}
    .ticker-content .ticker {{ vertical-align: middle; margin: 0 0.2rem; }}
    .ticker-content .price-up, .ticker-content .price-down {{ vertical-align: middle; margin-right: 0.5rem; }}
    @keyframes scroll-left {{ 0% {{ transform: translateX(0%); }} 100% {{ transform: translateX(-100%); }} }}

    /* Tabs Bloomberg */
    [data-baseweb="tab-list"] {{ background-color: {COLORS['bg_dark']}; border-bottom: 3px solid {COLORS['accent_orange']}; padding: 0; gap: 0; border-radius: 0; margin-bottom: 2rem; }}
    button[data-baseweb="tab"] {{ background-color: {COLORS['bg_dark']}; border: none; border-right: 1px solid {COLORS['border']}; color: {COLORS['text_secondary']}; font-family: 'Roboto Mono', monospace; font-weight: 600; font-size: 0.9rem; letter-spacing: 0.12em; text-transform: uppercase; padding: 1.2rem 2.5rem; transition: all 0.2s ease; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ background-color: {COLORS['accent_orange']}; color: {COLORS['bg_dark']}; border-bottom: none; box-shadow: 0 0 20px rgba(251, 139, 30, 0.5); font-weight: 700; }}
    button[data-baseweb="tab"]:hover:not([aria-selected="true"]) {{ background-color: {COLORS['bg_panel']}; color: {COLORS['text_primary']}; border-bottom: 2px solid {COLORS['accent_orange']}; }}

    /* Metrics Bloomberg Style */
    [data-testid="stMetric"] {{
        background: {COLORS['bg_panel']}; padding: 1.2rem 1.5rem; border: 2px solid {COLORS['border']};
        border-left: 4px solid {COLORS['accent_orange']}; border-radius: 0;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.8); transition: all 0.3s ease;
        margin-bottom: 1rem;
    }}
    [data-testid="stMetric"]:hover {{ border-left-color: {COLORS['success']}; border-left-width: 6px; box-shadow: 0 0 25px rgba(251, 139, 30, 0.4); transform: translateX(3px); background: {COLORS['bg_secondary']}; }}
    [data-testid="stMetric"] > label {{ color: {COLORS['text_secondary']} !important; font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 0.7rem; display: flex; justify-content: center; }}
    [data-testid="stMetric"] [data-testid="stMetricValue"] {{ color: {COLORS['text_primary']} !important; font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 2rem; text-shadow: 0 0 5px rgba(255, 255, 255, 0.3); display: flex; justify-content: center; }}
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {{ display: flex; justify-content: center; }}

    /* Section Titles */
    h2 {{
        color: {COLORS['accent_orange']}; text-transform: uppercase; text-align: center;
        border-bottom: 2px solid {COLORS['accent_orange']}; border-left: none;
        padding-bottom: 0.8rem; padding-left: 0;
        margin: 3rem 0 2rem 0; font-size: 1.7rem;
        font-family: 'Roboto Mono', monospace; letter-spacing: 0.1em;
    }}
    h3 {{
        color: {COLORS['blue_bright']}; text-align: center; font-size: 1.3rem;
        margin-top: 2.5rem; margin-bottom: 1.5rem;
        padding-bottom: 0.6rem; border-bottom: 1px solid {COLORS['border']};
        font-family: 'Roboto Mono', monospace; letter-spacing: 0.08em;
    }}
    h4 {{
        color: {COLORS['text_secondary']}; font-size: 0.95rem; text-transform: uppercase;
        letter-spacing: 0.08em; font-family: 'Roboto Mono', monospace;
        text-align: center; margin-bottom: 1rem;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{ background: linear-gradient(180deg, {COLORS['bg_secondary']} 0%, {COLORS['bg_dark']} 100%); border-right: 2px solid {COLORS['border']}; }}
    [data-testid="stSidebar"] h3 {{ color: {COLORS['accent_orange']}; font-size: 1.1rem; border-bottom: 1px solid {COLORS['accent_orange']}; padding-bottom: 0.5rem; margin-bottom: 1rem; }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{ color: {COLORS['text_primary']}; }}
    /* Expanders */
    [data-testid="stExpander"] {{ background-color: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']}; border-left: 3px solid {COLORS['blue_bright']}; border-radius: 0; margin-bottom: 1rem; }}
    [data-testid="stExpander"] summary {{ color: {COLORS['text_primary']}; font-family: 'Roboto Mono', monospace; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* DataFrames */
    .stDataFrame {{ margin-bottom: 2rem; }}
    [data-testid="stDataFrame"] table thead tr th {{ background-color: {COLORS['bg_dark']} !important; color: {COLORS['accent_orange']} !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; border-bottom: 2px solid {COLORS['accent_orange']}; }}
    [data-testid="stDataFrame"] table tbody tr:hover {{ background-color: {COLORS['bg_secondary']}; }}

    /* Bloomberg Panel Style */
    .bloomberg-panel {{
        background: {COLORS['bg_panel']}; border: 2px solid {COLORS['border']};
        border-left: 4px solid {COLORS['blue_bright']}; padding: 1.5rem;
        margin-bottom: 1.5rem; box-shadow: 0 2px 15px rgba(0, 0, 0, 0.6);
    }}
    .bloomberg-panel h4 {{ text-align: left; margin-bottom: 1rem; margin-top: 0; border-bottom: none; }}

    /* Graphiques */
    .stpyplot {{ margin-bottom: 2rem; }}
    .stBarChart {{ margin-bottom: 2rem; }}

    /* Ticker Style */
    .ticker {{ font-family: 'Roboto Mono', monospace; color: {COLORS['accent_yellow']}; font-weight: 700; background-color: {COLORS['bg_dark']}; padding: 0.2rem 0.5rem; border: 1px solid {COLORS['border']}; display: inline-block; margin: 0 0.3rem; vertical-align: middle; }}
    /* Price up/down styles */
    .price-up {{ color: {COLORS['success']}; font-weight: 700; }}
    .price-down {{ color: {COLORS['danger']}; font-weight: 700; }}
    /* Progress Bar Style */
    /* ... */
    /* Separators */
    hr {{ border: none; border-top: 1px solid {COLORS['border']}; margin: 2.5rem 0; }}
    /* Paragraphs */
    p {{ color: {COLORS['text_primary']}; line-height: 1.6; }}
    .caption {{ color: {COLORS['text_secondary']}; font-family: 'Roboto Mono', monospace; font-size: 0.75rem; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Fonctions Utilitaires --- (Inchangées)

def calculate_daily_rates():
    """Calcule les taux journaliers en base 365."""
    cash_daily = (1 + CASH_RATE_ANNUAL) ** (1/CALENDAR_DAYS) - 1
    rf_daily = (1 + RISK_FREE_RATE_ANNUAL) ** (1/CALENDAR_DAYS) - 1
    mgmt_fee_daily = MANAGEMENT_FEE_ANNUAL / CALENDAR_DAYS
    return cash_daily, rf_daily, mgmt_fee_daily

def get_tickers_by_class(benchmark_df, available_columns):
    """Retourne les tickers par classe d'actif."""
    if 'BBG Ticker' not in benchmark_df.columns or 'Asset Class' not in benchmark_df.columns:
        st.error("Colonnes 'BBG Ticker' ou 'Asset Class' manquantes dans 'Benchmark'.")
        return {'action': [], 'bond': [], 'commodity': []}
    benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str).str.strip()
    asset_class_map = benchmark_df.set_index('BBG Ticker').loc[:, 'Asset Class']
    available_columns_str = [str(col).strip() for col in available_columns]
    return {
        'action': [t for t in asset_class_map[asset_class_map == 'Action'].index if t in available_columns_str],
        'bond': [t for t in asset_class_map[asset_class_map == 'Gov bond'].index if t in available_columns_str],
        'commodity': [t for t in asset_class_map[asset_class_map == 'Commodities'].index if t in available_columns_str]
    }

def calculate_indicators(returns, rf_daily_for_sharpe):
    """Calcule volatilité (annu TRADING_DAYS), Sharpe (annu TRADING_DAYS) et VaR."""
    if returns is None or returns.empty or len(returns) < 2: return {'Volatilité': np.nan, 'Sharpe': np.nan, 'VaR 99%': np.nan}
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    var = returns.quantile(0.01); sharpe = np.nan
    std_dev = returns.std()
    if std_dev != 0 and np.isfinite(std_dev):
        excess = returns - rf_daily_for_sharpe
        sharpe = (excess.mean() / std_dev) * np.sqrt(TRADING_DAYS)
    return {'Volatilité': vol, 'Sharpe': sharpe, 'VaR 99%': var}

def calculate_benchmark_returns(returns_period, tickers, cash_daily_rate):
    """Calcule les rendements BRUTS quotidiens du benchmark."""
    returns_by_class = {
        'Action': returns_period[tickers['action']].mean(axis=1) if tickers['action'] else pd.Series(0, index=returns_period.index),
        'Gov bond': returns_period[tickers['bond']].mean(axis=1) if tickers['bond'] else pd.Series(0, index=returns_period.index),
        'Commodities': returns_period[tickers['commodity']].mean(axis=1) if tickers['commodity'] else pd.Series(0, index=returns_period.index),
        'Cash': pd.Series(cash_daily_rate, index=returns_period.index)
    }
    common_index = returns_period.index; weighted_sum = pd.Series(0.0, index=common_index)
    for k, weight in BENCHMARK_WEIGHTS.items():
         if k in returns_by_class and not returns_by_class[k].empty: weighted_sum = weighted_sum.add(returns_by_class[k].reindex(common_index).fillna(0) * weight, fill_value=0)
    return weighted_sum

# --- Barre de progression HTML personnalisée ---
def create_progress_bar(label, value, color):
    """Crée une barre de progression HTML."""
    value = max(0.0, min(1.0, value))
    return f"""
    <div style='margin-bottom: 0.8rem;'>
        <div style='display: flex; justify-content: space-between; margin-bottom: 0.3rem;'>
            <span style='color: {COLORS['text_secondary']}; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;'>{label}</span>
            <span style='color: {color}; font-size: 0.8rem; font-weight: 700;'>{value:.1%}</span>
        </div>
        <div style='background: #0D0D0D; height: 8px; border: 1px solid {COLORS['border']};'>
            <div style='background: {color}; height: 100%; width: {value*100}%; transition: width 0.3s ease;'></div>
        </div>
    </div>
    """

# --- Fonctions de Chargement --- (Inchangées)
@st.cache_data(ttl=3600)
def load_data():
    """Charge les données depuis Google Drive."""
    try:
        benchmark_df = pd.read_excel(EXCEL_URL, sheet_name="Benchmark"); required_cols = ['BBG Ticker', 'Asset Class']
        if not all(col in benchmark_df.columns for col in required_cols): st.error(f"Colonnes manquantes dans 'Benchmark': {required_cols}"); return None, None, None
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str).str.strip(); benchmark_df = benchmark_df.dropna(subset=['BBG Ticker'])

        prices_df_raw = pd.read_excel(EXCEL_URL, sheet_name="Historique Prix", header=3)

        portfolio_df = pd.read_excel(EXCEL_URL, sheet_name="Portefeuille", skiprows=1)
        if len(portfolio_df.columns) < 6: st.error("'Portefeuille' sheet must have >= 6 columns."); return None, None, None
        ticker_col = portfolio_df.columns[2]; weight_col = portfolio_df.columns[5] # Col C, Col F
        portfolio_df = portfolio_df[[ticker_col, weight_col]].copy(); portfolio_df.columns = ['BBG Ticker', 'Weight']
        portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str).str.strip(); portfolio_df = portfolio_df.dropna(subset=['BBG Ticker'])
        portfolio_df['Weight'] = pd.to_numeric(portfolio_df['Weight'], errors='coerce'); portfolio_df = portfolio_df.dropna(subset=['Weight'])

        total = portfolio_df['Weight'].sum()
        if total <= 0: st.error("Sum of portfolio weights <= 0."); return None, None, None

        if np.isclose(total, 100.0, atol=1.0): portfolio_df['Weight'] /= 100.0
        elif not np.isclose(total, 1.0, atol=0.01): st.warning(f"Sum of weights ({total:.2f}) != 1 or 100. Normalizing..."); portfolio_df['Weight'] /= total

        final_sum = portfolio_df['Weight'].sum()
        if not np.isclose(final_sum, 1.0, atol=0.01): st.error(f"Weight normalization failed. Sum: {final_sum:.4f}"); return None, None, None

        return benchmark_df, prices_df_raw, portfolio_df

    except Exception as e: st.error(f"Error loading data: {e}"); return None, None, None

@st.cache_data
def process_prices(prices_df_raw):
    """Traite les données de prix."""
    if prices_df_raw is None: return None, None
    original_cols = prices_df_raw.columns.tolist(); date_col = original_cols[0]
    if len(prices_df_raw.index) > 1 and not pd.isna(prices_df_raw.iloc[1, 0]):
        candidate = prices_df_raw.iloc[1, 0]
        if isinstance(candidate, str) and 'date' in candidate.lower(): date_col = candidate; new_cols = original_cols.copy(); new_cols[0] = date_col; prices_df_raw.columns = new_cols
    prices_df = prices_df_raw.iloc[2:].copy()
    try: prices_df[date_col] = pd.to_datetime(prices_df[date_col]); prices_df = prices_df.set_index(date_col)
    except Exception as e: st.error(f"Date conversion error: {e}"); return None, None
    prices_numeric = prices_df.apply(pd.to_numeric, errors='coerce'); prices_clean = prices_numeric.copy().ffill().bfill()
    prices_clean.columns = prices_clean.columns.astype(str).str.strip()
    returns = prices_clean.pct_change().iloc[1:]
    return prices_clean, returns

@st.cache_data
def calculate_full_period_indicators(benchmark_df, prices_hist, returns_full):
    """Calcule les indicateurs sur toute la période."""
    # ... (fonction inchangée) ...
    if benchmark_df is None or prices_hist is None or returns_full is None: return None, None, None, None
    if returns_full.empty: st.error("No return data."); return None, None, None, None

    cash_daily_365, rf_daily_365, _ = calculate_daily_rates()
    tickers = get_tickers_by_class(benchmark_df, prices_hist.columns)
    all_tickers = tickers['action'] + tickers['bond'] + tickers['commodity']
    if not all_tickers: st.error("No valid asset tickers found."); return None, None, None, None
    # S'assurer que l'index est bien une chaîne avant de mapper
    benchmark_df_indexed = benchmark_df.set_index(benchmark_df['BBG Ticker'].astype(str))
    asset_class_map = benchmark_df_indexed['Asset Class']

    bench_returns = calculate_benchmark_returns(returns_full, tickers, cash_daily_365).fillna(0)
    bench_returns.name = "Benchmark_Returns"
    if bench_returns.empty: st.error("Benchmark returns calculation failed."); return None, None, None, None

    bench_ind_calc = calculate_indicators(bench_returns, rf_daily_365)
    bench_indicators_full = {
        'Volatilité Annuelle': bench_ind_calc['Volatilité'],
        'Ratio de Sharpe Annuel': bench_ind_calc['Sharpe'],
        'VaR 99% (1 jour)': bench_ind_calc['VaR 99%']
    }

    returns_aligned = returns_full[[str(t) for t in all_tickers]].loc[bench_returns.index]
    indicators_list = []
    for ticker_str in returns_aligned.columns:
        ticker = ticker_str
        Y = returns_aligned[ticker_str]
        common_idx = bench_returns.index.intersection(Y.dropna().index)
        if len(common_idx) < 2: continue
        Y_aligned = Y.loc[common_idx]; X_aligned = bench_returns.loc[common_idx].values.reshape(-1, 1)
        ind = calculate_indicators(Y_aligned, rf_daily_365);
        vol = ind['Volatilité']; var = ind['VaR 99%']; sharpe = ind['Sharpe']
        corr = np.nan; beta = np.nan; bench_vals = bench_returns.loc[common_idx]
        if np.isfinite(bench_vals).all() and np.isfinite(Y_aligned).all():
            # Utilisation ddof=0 pour population std dev si on considère les données comme la population entière
            if bench_vals.std(ddof=0) != 0 and Y_aligned.std(ddof=0) != 0:
                 with warnings.catch_warnings(): warnings.simplefilter("ignore"); corr = np.corrcoef(bench_vals, Y_aligned)[0, 1]
            if X_aligned.std(ddof=0) != 0:
                try: model = LinearRegression(); model.fit(X_aligned, Y_aligned); beta = model.coef_[0]
                except ValueError: beta = 0.0 # Cas où X ou Y sont constants

        # Récupération de la classe d'actif via .get() pour éviter KeyError si ticker inconnu
        asset_class = asset_class_map.get(ticker, 'N/A')
        indicators_list.append({'Ticker': ticker, 'Asset Class': asset_class, 'Volatilite Annuelle': vol, 'Beta (vs Benchmark)': beta, 'Correlation (vs Benchmark)': corr, 'VaR 99% (1 jour)': var, 'Sharpe Ratio Annuel': sharpe})

    indicators_df = pd.DataFrame(indicators_list); corr_matrix = returns_aligned.corr()
    return indicators_df, corr_matrix, bench_indicators_full, asset_class_map


#@st.cache_data # Cache peut être problématique ici
def calculate_current_weights_and_drift(initial_weights_df, benchmark_df, prices_hist):
    """Calcule les poids courants et la dérive par rapport aux poids initiaux."""
    if initial_weights_df is None or benchmark_df is None or prices_hist is None or prices_hist.empty:
        return None

    try:
        # S'assurer que START_DATE_SIMULATION est dans l'index des prix ou trouver la plus proche
        if START_DATE_SIMULATION not in prices_hist.index:
            actual_start_prices_date = prices_hist[prices_hist.index >= START_DATE_SIMULATION].index.min()
            if pd.isna(actual_start_prices_date):
                 st.error(f"Cannot find prices at or after simulation start date {START_DATE_SIMULATION.strftime('%Y-%m-%d')}")
                 return None
            start_prices = prices_hist.loc[actual_start_prices_date]
            #st.warning(f"Using prices from {actual_start_prices_date.strftime('%Y-%m-%d')} as start date was not found.") # Optionnel
        else:
             start_prices = prices_hist.loc[START_DATE_SIMULATION]

        latest_prices = prices_hist.iloc[-1]

        initial_weights_df['BBG Ticker'] = initial_weights_df['BBG Ticker'].astype(str)
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)

        weights_with_class = initial_weights_df.merge(
            benchmark_df[['BBG Ticker', 'Asset Class']],
            on='BBG Ticker',
            how='left'
        )

        drift_data = []
        total_current_value = 0

        start_fx = start_prices.get('EURUSD Curncy', np.nan)
        latest_fx = latest_prices.get('EURUSD Curncy', np.nan)

        for _, row in weights_with_class.iterrows():
            ticker = str(row['BBG Ticker'])
            initial_weight = row['Weight']
            asset_class = row['Asset Class'] if pd.notna(row['Asset Class']) else ('Cash' if CASH_TICKER_NAME.lower() == ticker.lower() else 'Unknown')

            initial_alloc_eur = initial_weight * INITIAL_NAV_EUR

            if ticker.lower() == CASH_TICKER_NAME.lower():
                init_qty = initial_alloc_eur
                current_value = initial_alloc_eur
                start_price = 1.0
                latest_price = 1.0
            elif ticker in start_prices.index and ticker in latest_prices.index and pd.notna(start_prices[ticker]) and start_prices[ticker] != 0:
                start_price = start_prices[ticker]
                latest_price = latest_prices[ticker]

                if asset_class == 'Commodities' and pd.notna(start_fx) and start_fx != 0 and pd.notna(latest_fx):
                     initial_alloc_usd = initial_alloc_eur / start_fx
                     init_qty = initial_alloc_usd / start_price if start_price != 0 else 0
                     current_value_usd = init_qty * latest_price
                     current_value = current_value_usd * latest_fx
                else:
                    init_qty = initial_alloc_eur / start_price if start_price != 0 else 0
                    current_value = init_qty * latest_price

            else:
                init_qty = 0
                current_value = 0
                start_price = np.nan
                latest_price = np.nan

            if pd.notna(current_value):
                 total_current_value += current_value

            drift_data.append({
                'Asset Class': asset_class, 'BBG Ticker': ticker,
                'Initial Weight': initial_weight, 'Current Value (EUR)': current_value
            })

        drift_df = pd.DataFrame(drift_data)

        if total_current_value != 0:
            drift_df['Current Weight'] = drift_df['Current Value (EUR)'] / total_current_value
        else:
            drift_df['Current Weight'] = 0.0

        drift_df['Drift'] = drift_df['Current Weight'] - drift_df['Initial Weight']

        drift_df_final = drift_df[[
            'Asset Class', 'BBG Ticker', 'Initial Weight', 'Current Weight', 'Drift'
        ]].copy()

        return drift_df_final

    except KeyError as e:
         st.error(f"Error calculating drift: Missing data for ticker {e} on start or latest date.")
         return None
    except Exception as e:
        st.error(f"Error calculating allocation drift: {e}")
        return None

def calculate_simulation_performance(portfolio_df, benchmark_df, returns_all, start_date):
    """Calcule les performances de simulation, gérant le cash explicite ET les frais, ET la contribution."""
    # ... (fonction inchangée depuis v2.5) ...
    if portfolio_df is None or benchmark_df is None or returns_all is None: return None, None, None, None, None
    returns_sim = returns_all[returns_all.index >= start_date].copy()
    if returns_sim.empty: st.warning(f"No data since {start_date.strftime('%Y-%m-%d')}."); return None, None, None, None, None

    cash_daily_365, rf_daily_365, mgmt_fee_daily_365 = calculate_daily_rates()
    tickers = get_tickers_by_class(benchmark_df, returns_sim.columns)

    # --- Benchmark Returns & NAV (Brut) ---
    bench_returns_gross = calculate_benchmark_returns(returns_sim, tickers, cash_daily_365).fillna(0)
    actual_start_brut = bench_returns_gross.index.min()
    actual_start = start_date
    if start_date not in bench_returns_gross.index:
         bench_returns_gross.loc[start_date] = 0.0
         bench_returns_gross = bench_returns_gross.sort_index()

    nav_bench_raw = (1 + bench_returns_gross).cumprod(); nav_bench = nav_bench_raw * 100; nav_bench.name = "Benchmark"

    # --- Portfolio Returns (Brut) & NAV (Net de frais) ---
    weights_dict = portfolio_df.set_index('BBG Ticker')['Weight'].to_dict()

    cash_weight_explicit = 0.0; cash_ticker_found = None
    for ticker, weight in weights_dict.items():
        if CASH_TICKER_NAME.lower() == str(ticker).lower():
            cash_weight_explicit = weight; cash_ticker_found = ticker; break

    portfolio_asset_tickers = [t for t in weights_dict.keys() if str(t) in returns_sim.columns and (cash_ticker_found is None or str(t).lower() != str(cash_ticker_found).lower())]
    portfolio_returns_raw = returns_sim[[str(t) for t in portfolio_asset_tickers]]
    aligned_weights = pd.Series({t: weights_dict[t] for t in portfolio_asset_tickers})
    weighted_asset_returns = portfolio_returns_raw.multiply(aligned_weights, axis=1).sum(axis=1).fillna(0)
    portfolio_returns_gross = weighted_asset_returns + (cash_weight_explicit * cash_daily_365)

    if start_date not in portfolio_returns_gross.index:
        portfolio_returns_gross.loc[start_date] = 0.0
        portfolio_returns_gross = portfolio_returns_gross.sort_index()

    nav_portfolio = pd.Series(index=portfolio_returns_gross.index, dtype=float)
    nav_portfolio.loc[start_date] = 100.0
    start_loc = portfolio_returns_gross.index.get_loc(start_date)
    for i in range(start_loc + 1, len(portfolio_returns_gross)):
         current_date = portfolio_returns_gross.index[i]
         previous_date = portfolio_returns_gross.index[i-1]
         prev_nav = nav_portfolio.loc[previous_date] if previous_date in nav_portfolio.index else nav_portfolio.iloc[i-1]
         daily_gross_return = portfolio_returns_gross.loc[current_date]
         current_nav = prev_nav * (1 + daily_gross_return) * (1 - mgmt_fee_daily_365)
         nav_portfolio.loc[current_date] = current_nav
    nav_portfolio.name = "Votre Fonds (Net)"
    nav_portfolio = nav_portfolio.ffill()

    # --- Calcul Contribution P&L (Brut) ---
    pnl_contributions = []
    if not isinstance(benchmark_df.index, pd.Index) or benchmark_df.index.name != 'BBG Ticker':
         benchmark_df_indexed_contrib = benchmark_df.set_index(benchmark_df['BBG Ticker'].astype(str))
    else: benchmark_df_indexed_contrib = benchmark_df
    asset_class_map_contrib = benchmark_df_indexed_contrib['Asset Class']
    sim_period_returns_contrib = returns_sim[returns_sim.index >= start_date] # Contribution depuis start_date

    for ticker, initial_weight in weights_dict.items():
        ticker_str = str(ticker)
        asset_class = asset_class_map_contrib.get(ticker_str, 'Cash' if CASH_TICKER_NAME.lower() == ticker_str.lower() else 'Unknown')
        initial_value = initial_weight * 100

        if ticker_str == cash_ticker_found:
             relevant_dates = returns_all[returns_all.index >= start_date].index
             num_days = len(relevant_dates)
             final_value = initial_value * ((1 + cash_daily_365) ** num_days)
             pnl = final_value - initial_value
        elif ticker_str in sim_period_returns_contrib.columns:
             cum_ret_asset = (1 + sim_period_returns_contrib[ticker_str]).prod() - 1
             final_value = initial_value * (1 + cum_ret_asset)
             pnl = final_value - initial_value
        else: pnl = 0

        pnl_contributions.append({'Asset Class': asset_class, 'P&L Contribution (Base 100)': pnl})

    contribution_df = pd.DataFrame(pnl_contributions)
    # S'assurer que 'Asset Class' est bien la colonne pour groupby
    if 'Asset Class' in contribution_df.columns:
        contribution_by_class = contribution_df.groupby('Asset Class')['P&L Contribution (Base 100)'].sum().reset_index()
    else:
        contribution_by_class = pd.DataFrame(columns=['Asset Class', 'P&L Contribution (Base 100)']) # DataFrame vide


    # --- Indicateurs & TE ---
    portfolio_returns_net = nav_portfolio.pct_change().fillna(0)
    sim_indicators = {"benchmark": {}, "portfolio": {}}; te_series = None; avg_te = np.nan
    bench_rets_stats = bench_returns_gross[bench_returns_gross.index > start_date]
    port_rets_stats = portfolio_returns_net[portfolio_returns_net.index > start_date]

    if len(bench_rets_stats) >= 1:
        sim_indicators['benchmark'] = calculate_indicators(bench_rets_stats, rf_daily_365)
        sim_indicators['portfolio'] = calculate_indicators(port_rets_stats, rf_daily_365)
        if len(bench_rets_stats) >= 2:
            common_te_index = bench_rets_stats.index.intersection(port_rets_stats.index)
            # S'assurer qu'il y a des données communes pour calculer diff
            if not common_te_index.empty:
                diff = port_rets_stats.loc[common_te_index] - bench_rets_stats.loc[common_te_index]
                if len(diff) >= 2:
                    avg_te = diff.std() * np.sqrt(TRADING_DAYS)
                    window = 60
                    if len(diff) >= window:
                        te_series = diff.rolling(window=window).std() * np.sqrt(TRADING_DAYS)
                        te_series = te_series.dropna(); te_series.name = "Tracking Error (60j)"
                        if not te_series.empty: avg_te = te_series.mean()
            # else: avg_te = np.nan # Pas de données communes

    comparison = pd.DataFrame({'Benchmark': nav_bench, 'Votre Fonds (Net)': nav_portfolio})
    if start_date in comparison.index: comparison.loc[start_date] = 100.0
    else: comparison.loc[start_date] = 100.0; comparison = comparison.sort_index()
    comparison = comparison.ffill()

    return comparison, sim_indicators, te_series, avg_te, contribution_by_class


# --- Interface ---

st.markdown(f"""
<div class="bloomberg-header">
    <h1>⬛ M2 MBFA TERMINAL</h1>
    <div class="subtitle">PORTFOLIO ANALYTICS & RISK MANAGEMENT SYSTEM | {datetime.now().strftime('%d %b %Y %H:%M:%S')}</div>
</div>
""", unsafe_allow_html=True)

# --- Data Loading & Processing ---
with st.spinner("LOADING MARKET DATA... PLEASE WAIT..."):
    benchmark_df, prices_raw, portfolio_df = load_data()
    if benchmark_df is None or prices_raw is None or portfolio_df is None: st.error("Critical data loading failed."); st.stop()
    prices_hist, returns_all = process_prices(prices_raw)
    if prices_hist is None or returns_all is None: st.error("Failed to process price data."); st.stop()
    indicators_full, corr_matrix, bench_indicators_full, asset_map = calculate_full_period_indicators(benchmark_df, prices_hist, returns_all)
    if indicators_full is None: st.error("Failed to calculate full period indicators."); st.stop()
    drift_df = calculate_current_weights_and_drift(portfolio_df, benchmark_df, prices_hist)


# --- Market Movers Ticker HTML Generation --- (Inchangé)
if returns_all is not None and not returns_all.empty:
    try:
        latest_date = returns_all.index[-1]
        latest_returns = returns_all.iloc[-1].dropna()

        if benchmark_df is not None:
             investment_universe = benchmark_df['BBG Ticker'].astype(str).str.strip().tolist()
             valid_tickers = [t for t in latest_returns.index if t in investment_universe]
             latest_returns = latest_returns[valid_tickers]

        if not latest_returns.empty:
            top_gainers = latest_returns.nlargest(3)
            top_losers = latest_returns.nsmallest(3)

            ticker_html = f"<div class='market-ticker'>"
            ticker_html += f"<span class='ticker-label'>MARKET MOVERS | {latest_date.strftime('%d %b %Y')}</span>"
            ticker_html += "<div class='ticker-wrap'>"
            ticker_html += "<span class='ticker-content'>"

            ticker_html += f"<strong style='color: {COLORS['success']};'>TOP GAINERS:</strong> "
            gainer_strings = []
            for ticker, val in top_gainers.items():
                 gainer_strings.append(f"<span class='ticker'>{ticker}</span> <span class='price-up'>{val:+.2%}</span>")
            ticker_html += "&nbsp;|&nbsp;".join(gainer_strings)

            ticker_html += f"&nbsp;&nbsp;&nbsp;&nbsp;<strong style='color: {COLORS['danger']};'>TOP LOSERS:</strong> "
            loser_strings = []
            for ticker, val in top_losers.items():
                 loser_strings.append(f"<span class='ticker'>{ticker}</span> <span class='price-down'>{val:+.2%}</span>")
            ticker_html += "&nbsp;|&nbsp;".join(loser_strings)

            ticker_html += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            ticker_html += f"<strong style='color: {COLORS['success']};'>TOP GAINERS:</strong> " + "&nbsp;|&nbsp;".join(gainer_strings)
            ticker_html += f"&nbsp;&nbsp;&nbsp;&nbsp;<strong style='color: {COLORS['danger']};'>TOP LOSERS:</strong> " + "&nbsp;|&nbsp;".join(loser_strings)

            ticker_html += "</span></div></div>"
            st.markdown(ticker_html, unsafe_allow_html=True)

    except Exception as e:
        pass
# --- FIN Market Movers ---

# --- Calcul des poids du portefeuille pour la barre latérale --- (Inchangé)
portfolio_class_weights = {}
if portfolio_df is not None and benchmark_df is not None:
    portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str)
    benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)
    display_weights_sidebar = portfolio_df.merge(benchmark_df[['BBG Ticker', 'Asset Class']], on='BBG Ticker', how='left')
    cash_row_sidebar = display_weights_sidebar[display_weights_sidebar['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
    explicit_cash_weight_sidebar = cash_row_sidebar['Weight'].sum() if not cash_row_sidebar.empty else 0.0
    non_cash_weights_sidebar = display_weights_sidebar[~display_weights_sidebar['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
    if 'Asset Class' in display_weights_sidebar.columns:
        class_weights_sidebar = non_cash_weights_sidebar.groupby('Asset Class')['Weight'].sum()
        portfolio_class_weights = class_weights_sidebar.to_dict()
    if explicit_cash_weight_sidebar > 0.0001:
        portfolio_class_weights['Cash'] = explicit_cash_weight_sidebar

# --- Barre Latérale (Sidebar) --- (Inchangé)
st.sidebar.markdown("### SYSTEM PARAMETERS")

with st.sidebar.expander("PORTFOLIO COMPOSITION", expanded=True):
    st.markdown("**YOUR ALLOCATION**")
    bars = create_progress_bar("EQUITY", portfolio_class_weights.get('Action', 0.0), COLORS['danger'])
    bars += create_progress_bar("BONDS", portfolio_class_weights.get('Gov bond', 0.0), COLORS['blue_bright'])
    bars += create_progress_bar("CMDTY", portfolio_class_weights.get('Commodities', 0.0), COLORS['accent_orange'])
    bars += create_progress_bar("CASH", portfolio_class_weights.get('Cash', 0.0), COLORS['success'])
    st.markdown(bars, unsafe_allow_html=True)

with st.sidebar.expander("BENCHMARK COMPOSITION", expanded=True):
    st.markdown("**60/20/15/5 STRATEGY**")
    bench_bars = create_progress_bar("EQUITY", BENCHMARK_WEIGHTS['Action'], COLORS['danger'])
    bench_bars += create_progress_bar("BONDS", BENCHMARK_WEIGHTS['Gov bond'], COLORS['blue_bright'])
    bench_bars += create_progress_bar("CMDTY", BENCHMARK_WEIGHTS['Commodities'], COLORS['accent_orange'])
    bench_bars += create_progress_bar("CASH", BENCHMARK_WEIGHTS['Cash'], COLORS['success'])
    st.markdown(bench_bars, unsafe_allow_html=True)

with st.sidebar.expander("RISK-FREE & CASH RATE", expanded=True):
    st.metric("ANNUAL RATE", f"{RISK_FREE_RATE_ANNUAL:.1%}", help="Used for Sharpe Ratio calculation.");
    st.caption(f"CASH REMUNERATION: {CASH_RATE_ANNUAL:.1%}, BASIS: {CALENDAR_DAYS} DAYS")

with st.sidebar.expander("FEES", expanded=True):
     st.metric("MANAGEMENT (ANNUAL)", f"{MANAGEMENT_FEE_ANNUAL:.2%}", help=f"Deducted daily from portfolio NAV based on {CALENDAR_DAYS} days.")
     st.metric("TRANSACTION (PER TRADE)", f"{TRANSACTION_FEE_RATE:.2%}", help="Applied on buy/sell nominal. Not applied in current simulation.")

with st.sidebar.expander("DATA SOURCE", expanded=True):
    st.info("**SOURCE**: Google Sheets\n\n**PORTFOLIO**: Col C (Ticker) & F (Weight)")
    st.caption(f"LAST UPDATE: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["MONITOR", "HOLDINGS", "ANALYTICS"])

# --- TAB 1: MONITOR ---
with tab1:
    st.markdown(f"## PERFORMANCE ANALYSIS: {START_DATE_SIMULATION.strftime('%d/%b/%Y')} - PRESENT")
    comparison, sim_ind, te_series, avg_te, contribution_by_class = calculate_simulation_performance(portfolio_df, benchmark_df, returns_all, START_DATE_SIMULATION)

    # Quick Stats Section (inchangé)
    st.markdown("### QUICK STATS")
    if comparison is not None and not comparison.empty:
        try:
            latest_nav_bench = comparison['Benchmark'].iloc[-1]
            latest_nav_port = comparison['Votre Fonds (Net)'].iloc[-1]
            perf_bench = (latest_nav_bench / 100) - 1
            perf_port = (latest_nav_port / 100) - 1
            outperformance = perf_port - perf_bench

            qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
            qcol1.metric("PORTFOLIO NAV (NET)", f"{latest_nav_port:.2f}", f"{perf_port:+.2%}")
            qcol2.metric("BENCHMARK NAV", f"{latest_nav_bench:.2f}", f"{perf_bench:+.2%}")
            delta_perf_display = f"{outperformance:+.2%}"
            qcol3.metric("OUTPERFORMANCE", delta_perf_display)

            if sim_ind:
                qcol4.metric("VOL (PORT., ANN.)", f"{sim_ind['portfolio']['Volatilité']:.2%}" if pd.notna(sim_ind['portfolio'].get('Volatilité')) else "N/A", help=f"Annualized on {TRADING_DAYS}d, Net Returns")
                qcol5.metric("SHARPE (PORT., ANN.)", f"{sim_ind['portfolio']['Sharpe']:.3f}" if pd.notna(sim_ind['portfolio'].get('Sharpe')) else "N/A", help=f"Annualized on {TRADING_DAYS}d, Net Returns vs {RISK_FREE_RATE_ANNUAL:.1%} Rf")
        except Exception as e:
            st.warning(f"Could not display Quick Stats: {e}")
            pass
    else:
        st.warning("Quick Stats unavailable (no simulation data).")
    st.markdown("---")


    # --- MODIFIED: Section Contribution à la Performance ---
    st.markdown("### PERFORMANCE CONTRIBUTION (GROSS, BASE 100)")
    if contribution_by_class is not None and not contribution_by_class.empty:
         # S'assurer que les colonnes nécessaires existent
         if 'Asset Class' in contribution_by_class.columns and 'P&L Contribution (Base 100)' in contribution_by_class.columns:
              # Utiliser directement le DataFrame avec les colonnes spécifiées pour le bar chart
              # Streamlit choisira les couleurs par défaut basées sur 'Asset Class'
              st.bar_chart(contribution_by_class.set_index('Asset Class')['P&L Contribution (Base 100)']) # Index par Asset Class

              # Afficher le tableau récapitulatif
              st.dataframe(contribution_by_class.style.format({'P&L Contribution (Base 100)': '{:+.2f}'}), use_container_width=True)
              st.caption("Contribution based on initial weights and cumulative gross asset returns (fees excluded).")
         else:
              st.warning("Contribution data is missing required columns ('Asset Class', 'P&L Contribution (Base 100)').")
    else:
         st.warning("Performance contribution data unavailable.")
    st.markdown("---")
    # --- FIN MODIFICATION ---


    if sim_ind:
        st.markdown("### KEY PERFORMANCE INDICATORS (SIMULATION PERIOD)")
        # ... (KPIs section inchangée) ...
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### BENCHMARK (GROSS)")
            subcol1, subcol2, subcol3 = st.columns(3)
            subcol1.metric("VOL (ANN.)", f"{sim_ind['benchmark']['Volatilité']:.2%}" if pd.notna(sim_ind['benchmark']['Volatilité']) else "N/A", help=f"Annualized on {TRADING_DAYS} days")
            subcol2.metric("SHARPE (ANN.)", f"{sim_ind['benchmark']['Sharpe']:.3f}" if pd.notna(sim_ind['benchmark']['Sharpe']) else "N/A", help=f"Annualized on {TRADING_DAYS} days vs {RISK_FREE_RATE_ANNUAL:.1%} Rf")
            subcol3.metric("VAR 99% (1D)", f"{sim_ind['benchmark']['VaR 99%']:.2%}" if pd.notna(sim_ind['benchmark']['VaR 99%']) else "N/A")
        with col2:
            st.markdown("#### PORTFOLIO (NET OF MGMT FEES)")
            subcol1, subcol2, subcol3 = st.columns(3)
            subcol1.metric("VOL (ANN.)", f"{sim_ind['portfolio']['Volatilité']:.2%}" if pd.notna(sim_ind['portfolio']['Volatilité']) else "N/A", help=f"Annualized on {TRADING_DAYS} days")
            subcol2.metric("SHARPE (ANN.)", f"{sim_ind['portfolio']['Sharpe']:.3f}" if pd.notna(sim_ind['portfolio']['Sharpe']) else "N/A", help=f"Annualized on {TRADING_DAYS} days vs {RISK_FREE_RATE_ANNUAL:.1%} Rf")
            subcol3.metric("VAR 99% (1D)", f"{sim_ind['portfolio']['VaR 99%']:.2%}" if pd.notna(sim_ind['portfolio']['VaR 99%']) else "N/A")
    st.markdown("---")

    st.markdown("### BENCHMARK REFERENCE (FULL PERIOD, GROSS)")
    if bench_indicators_full:
        col1, col2, col3 = st.columns(3)
        col1.metric("VOLATILITY", f"{bench_indicators_full['Volatilité Annuelle']:.2%}" if pd.notna(bench_indicators_full['Volatilité Annuelle']) else "N/A")
        col2.metric("SHARPE RATIO", f"{bench_indicators_full['Ratio de Sharpe Annuel']:.3f}" if pd.notna(bench_indicators_full['Ratio de Sharpe Annuel']) else "N/A")
        col3.metric("VAR 99% (1D)", f"{bench_indicators_full['VaR 99% (1 jour)']:.2%}" if pd.notna(bench_indicators_full['VaR 99% (1 jour)']) else "N/A")
    st.markdown("---")

    st.markdown("### PERFORMANCE CHART & TRACKING ERROR")
    if comparison is not None:
        fig, ax1 = plt.subplots(figsize=(14, 7)); fig.patch.set_facecolor(COLORS['bg_dark']); ax1.set_facecolor(COLORS['bg_panel'])
        ax1.plot(comparison.index, comparison['Benchmark'], color=COLORS['blue_bright'], linewidth=2.5, linestyle='--', label='BENCHMARK (GROSS)', alpha=0.9)
        ax1.plot(comparison.index, comparison['Votre Fonds (Net)'], color=COLORS['accent_orange'], linewidth=2.5, label='PORTFOLIO (NET)', alpha=0.9)
        ax1.set_ylabel("NAV (BASE 100)", fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax1.set_xlabel("DATE", fontsize=10, fontweight='500', color=COLORS['text_secondary']); ax1.tick_params(axis='y', labelcolor=COLORS['text_primary'], colors=COLORS['text_primary']); ax1.tick_params(axis='x', labelcolor=COLORS['text_secondary'], colors=COLORS['text_secondary'])
        min_val = comparison.min().min() if not comparison.empty else 90
        max_val = comparison.max().max() if not comparison.empty else 110
        ax1.set_ylim(bottom=max(80, min_val - 2), top=min(120, max_val + 2))

        ax1.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid']); ax1.spines['bottom'].set_color(COLORS['border']); ax1.spines['top'].set_color(COLORS['border']); ax1.spines['left'].set_color(COLORS['border']); ax1.spines['right'].set_color(COLORS['border'])
        ax2 = ax1.twinx(); ax2.set_ylabel('TRACKING ERROR (ANN %)', fontsize=11, fontweight='600', color=COLORS['accent_yellow'], fontfamily='monospace'); ax2.tick_params(axis='y', labelcolor=COLORS['accent_yellow'], colors=COLORS['accent_yellow']); ax2.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
        lines = []; labels = []; lines1, labels1 = ax1.get_legend_handles_labels(); lines.extend(lines1); labels.extend(labels1)
        if te_series is not None and not te_series.empty:
            te_plot = te_series
            line_te, = ax2.plot(te_plot.index, te_plot, color=COLORS['accent_yellow'], linewidth=2, label='TE 60D', alpha=0.8)
            lines.append(line_te); labels.append(f'TE {TRADING_DAYS}D ANN. (60D ROLL)'); max_te_val = te_plot.max(); ax2.set_ylim(0, max(0.05, np.ceil((max_te_val if pd.notna(max_te_val) else 0)*100)/100 + 0.01))
        elif not np.isnan(avg_te) and avg_te >= 0:
            line_te = ax2.axhline(avg_te, color=COLORS['accent_yellow'], linestyle=':', linewidth=2, label=f'AVG TE ({avg_te:.2%})', alpha=0.8)
            lines.append(line_te); labels.append(f'AVG TE ({avg_te:.2%})'); ax2.set_ylim(0, max(0.05, np.ceil(avg_te*100)/100 + 0.01))
        else: ax2.set_yticks([])
        ax1.legend(lines, labels, loc='upper left', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9, labelcolor=COLORS['text_primary'])
        plt.title("PERFORMANCE MONITOR (PORTFOLIO NET vs BENCHMARK GROSS)", fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); plt.xticks(rotation=45, fontsize=8); fig.tight_layout(); st.pyplot(fig)
        if not np.isnan(avg_te):
            col1, col2, col3 = st.columns([1, 1, 1]);
            with col2: st.metric("AVG TRACKING ERROR", f"{avg_te:.2%}", help=f"Rolling 60d (or overall) annualized ({TRADING_DAYS}d) TE of Net Portfolio vs Gross Benchmark")
    else: st.warning("SIMULATION DATA UNAVAILABLE")

# --- TAB 2: HOLDINGS ---
with tab2:
    st.markdown("## PORTFOLIO HOLDINGS")
    if portfolio_df is not None and benchmark_df is not None:
        st.markdown("### PORTFOLIO SUMMARY")
        portfolio_df['BBG Ticker'] = portfolio_df['BBG Ticker'].astype(str)
        benchmark_df['BBG Ticker'] = benchmark_df['BBG Ticker'].astype(str)
        display_weights = portfolio_df.merge(benchmark_df[['BBG Ticker', 'Asset Class']], on='BBG Ticker', how='left'); display_weights = display_weights[['Asset Class', 'BBG Ticker', 'Weight']]

        cash_row = display_weights[display_weights['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]
        explicit_cash_weight = cash_row['Weight'].sum() if not cash_row.empty else 0.0
        non_cash_weights = display_weights[~display_weights['BBG Ticker'].str.contains(CASH_TICKER_NAME, case=False, na=False)]

        col1, col2, col3, col4 = st.columns(4);
        col1.metric("POSITIONS", len(non_cash_weights) + (1 if explicit_cash_weight > 0 else 0) )
        col2.metric("ASSET WEIGHT", f"{non_cash_weights['Weight'].sum():.1%}")
        col3.metric("CASH WEIGHT", f"{explicit_cash_weight:.2%}", help="Explicitly defined in 'Portefeuille' sheet")
        avg_weight = non_cash_weights['Weight'].mean() if not non_cash_weights.empty else 0.0
        col4.metric("AVG ASSET WGHT", f"{avg_weight:.2%}")

        st.markdown("---")
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.markdown("#### POSITION DETAILS")
            df_display = pd.concat([non_cash_weights, cash_row]).reset_index(drop=True)
            styled_df = df_display.style.format({'Weight': '{:.2%}'}).background_gradient(subset=['Weight'], cmap='YlOrRd', vmin=0, vmax=max(0.01, df_display['Weight'].max()))
            st.dataframe(styled_df, use_container_width=True, height=400)
        with col_right:
            st.markdown("#### ASSET CLASS BREAKDOWN")
            if 'Asset Class' in display_weights.columns:
                class_weights = non_cash_weights.groupby('Asset Class')['Weight'].sum().sort_values(ascending=False);
                for asset_class, weight in class_weights.items(): st.metric(asset_class.upper(), f"{weight:.2%}")
                if explicit_cash_weight > 0.0001: st.metric("CASH", f"{explicit_cash_weight:.2%}")
            else: st.warning("Asset class data unavailable")
        st.markdown("---")

# --- Section Allocation Drift ---
        st.markdown("### ALLOCATION DRIFT ANALYSIS")
        if drift_df is not None:
            latest_drift_date = prices_hist.index[-1].strftime('%d %b %Y') if prices_hist is not None else "N/A"
            st.caption(f"Comparison of current weights (as of {latest_drift_date}) vs initial weights at start.")

            # --- MODIFIED: Correction application style pour Styler ---
            def color_drift_styler(val):
                """Applies color based on drift value for Styler."""
                if pd.isna(val):
                    return '' # No style for NaN
                # Seuil plus petit pour colorer même les petites dérives
                threshold = 0.0001
                color = COLORS['danger'] if val < -threshold else COLORS['success'] if val > threshold else COLORS['text_secondary']
                return f'color: {color}; font-weight: bold;'

            styled_drift_df = drift_df.style.format({
                'Initial Weight': '{:.2%}',
                'Current Weight': '{:.2%}',
                'Drift': '{:+.2%}' # Ajoute le signe + ou -
            }).apply(lambda s: s.map(color_drift_styler), subset=['Drift']) # Use apply with map on subset 'Drift'
            # --- FIN MODIFICATION ---

            st.dataframe(styled_drift_df, use_container_width=True, height=450)

            st.markdown("#### DRIFT VISUALIZATION (vs Initial)")
            # --- MODIFIED: Simplification pour st.bar_chart ---
            # Préparer les données (index=Ticker, valeur=Drift)
            drift_chart_data = drift_df.set_index('BBG Ticker')['Drift']
            # Ne pas passer l'argument color pour laisser Streamlit gérer
            st.bar_chart(drift_chart_data)
            # --- FIN MODIFICATION ---

        else:
            st.warning("Allocation drift data unavailable.")
        st.markdown("---")
        # --- FIN Section Allocation Drift ---


        st.markdown("### ALLOCATION VISUALIZATION (Current)")
        if 'Asset Class' in display_weights.columns:
            current_class_weights = non_cash_weights.groupby('Asset Class')['Weight'].sum();
            if explicit_cash_weight > 0.0001: current_class_weights['Cash'] = explicit_cash_weight
            class_data_pie = current_class_weights[current_class_weights > 0]

            if not class_data_pie.empty:
                fig_pie, ax_pie = plt.subplots(figsize=(10, 6)); fig_pie.patch.set_facecolor(COLORS['bg_dark']); ax_pie.set_facecolor(COLORS['bg_dark'])
                colors_pie = [COLORS['danger'], COLORS['blue_bright'], COLORS['accent_orange'], COLORS['success'], COLORS['accent_yellow']]
                wedges, texts, autotexts = ax_pie.pie(class_data_pie.values, labels=class_data_pie.index, autopct='%1.1f%%', colors=colors_pie[:len(class_data_pie)], startangle=90, textprops={'fontsize': 10, 'fontweight': '600', 'color': COLORS['text_primary'], 'fontfamily': 'monospace'})
                for autotext in autotexts: autotext.set_color(COLORS['bg_dark']); autotext.set_fontweight('bold'); autotext.set_fontsize(11)
                ax_pie.set_title("CURRENT ASSET CLASS ALLOCATION", fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); st.pyplot(fig_pie)
            else: st.warning("No allocation data.")
        st.markdown("---")
        st.markdown("### MANAGEMENT RULES & CONSTRAINTS")
        st.markdown(f"""
        <div class='bloomberg-panel'>
            <h4>Mandate Rules Summary</h4>
            <ul>
                <li><strong>Management Fees:</strong> {MANAGEMENT_FEE_ANNUAL:.2%} p.a. (deducted daily)</li>
                <li><strong>Cash Remuneration:</strong> {CASH_RATE_ANNUAL:.2%} p.a. (applied daily)</li>
                <li><strong>Transaction Fees:</strong> {TRANSACTION_FEE_RATE:.2%} per trade (buy/sell). <span style='color:{COLORS['text_secondary']};'>*Note: Not applied in current NAV simulation.*</span></li>
                <li><strong>Overdraft Facility:</strong> Up to 20% allowed (subject to costs).</li>
                <li><strong>Risk Calculation (if Leveraged):</strong> VaR (1d, 99%) mandatory.</li>
                <li><strong>Trading Basis:</strong> Closing prices.</li>
                <li><strong>Universe:</strong> Benchmark components only.</li>
                <li><strong>Objective:</strong> Beat the benchmark.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.warning("""**TRANSACTION SIMULATOR**\n\n*UNDER DEVELOPMENT*\n\nAvailable soon for strategy testing.""")
    else: st.error("PORTFOLIO DATA UNAVAILABLE")


# --- TAB 3: ANALYTICS --- (Inchangé)
with tab3:
    st.markdown("## ASSET ANALYTICS")
    if indicators_full is not None and corr_matrix is not None and bench_indicators_full is not None:
        subtab1, subtab2, subtab3 = st.tabs(["INDICATORS", "VISUAL ANALYSIS", "CORRELATION"])
        with subtab1:
            st.markdown("### ASSET CHARACTERISTICS"); st.caption("Calculated over full historical period")
            col1, col2, col3, col4 = st.columns(4); col1.metric("ASSETS ANALYZED", len(indicators_full))
            avg_vol = indicators_full['Volatilite Annuelle'].mean(); col2.metric("AVG VOL (ANN.)", f"{avg_vol:.2%}")
            avg_sharpe = indicators_full['Sharpe Ratio Annuel'].mean(); col3.metric("AVG SHARPE (ANN.)", f"{avg_sharpe:.3f}")
            avg_beta = indicators_full['Beta (vs Benchmark)'].mean(); col4.metric("AVG BETA", f"{avg_beta:.2f}")
            st.markdown("---")
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1: asset_classes = ['ALL'] + sorted(list(indicators_full['Asset Class'].dropna().unique())); selected_class = st.selectbox("FILTER BY ASSET CLASS", asset_classes, key="filter_indicators")
            with col_filter2: sort_by = st.selectbox("SORT BY", ['Ticker', 'Volatilite Annuelle', 'Sharpe Ratio Annuel', 'Beta (vs Benchmark)'], key="sort_indicators")
            if selected_class == 'ALL': filtered_df = indicators_full.copy()
            else: filtered_df = indicators_full[indicators_full['Asset Class'] == selected_class].copy()
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=(sort_by != 'Sharpe Ratio Annuel'))
            styled_indicators = filtered_df.style.format({
                'Volatilite Annuelle': '{:.2%}', 'Beta (vs Benchmark)': '{:.2f}',
                'Correlation (vs Benchmark)': '{:.2f}', 'VaR 99% (1 jour)': '{:.2%}',
                'Sharpe Ratio Annuel': '{:.3f}'
            }, na_rep='N/A').background_gradient(
                subset=['Sharpe Ratio Annuel'], cmap='RdYlGn', vmin=-1, vmax=2
            ).background_gradient(
                subset=['Volatilite Annuelle'], cmap='Reds', vmin=0, vmax=max(0.01, filtered_df['Volatilite Annuelle'].max()) if not filtered_df.empty else 1
            ).background_gradient(
                 subset=['Beta (vs Benchmark)'], cmap='coolwarm', vmin=min(0, filtered_df['Beta (vs Benchmark)'].min()), vmax=max(1.5, filtered_df['Beta (vs Benchmark)'].max())
            ).background_gradient(
                 subset=['Correlation (vs Benchmark)'], cmap='coolwarm', vmin=-1, vmax=1
            )

            st.dataframe(styled_indicators, use_container_width=True, height=500)
            csv = filtered_df.to_csv(index=False).encode('utf-8'); st.download_button("DOWNLOAD CSV", csv, f"indicators_{selected_class.lower()}.csv", "text/csv", key='download_indicators')
        with subtab2:
            st.markdown("### RISK-RETURN ANALYSIS")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2: asset_classes_viz = ['ALL'] + sorted(list(indicators_full['Asset Class'].dropna().unique())); selected_class_viz = st.selectbox("FILTER BY CLASS", asset_classes_viz, key="filter_viz")
            if selected_class_viz == 'ALL': data_plot = indicators_full.dropna(subset=['Beta (vs Benchmark)', 'Volatilite Annuelle'])
            else: data_plot = indicators_full[indicators_full['Asset Class'] == selected_class_viz].dropna(subset=['Beta (vs Benchmark)', 'Volatilite Annuelle'])
            st.info(f"Displaying **{len(data_plot)}** assets")
            if not data_plot.empty:
                fig_scatter, ax_scatter = plt.subplots(figsize=(12, 7)); fig_scatter.patch.set_facecolor(COLORS['bg_dark']); ax_scatter.set_facecolor(COLORS['bg_panel'])
                class_colors = {'Action': COLORS['danger'], 'Gov bond': COLORS['success'], 'Commodities': COLORS['accent_orange']} # Rouge, Turquoise, Orange
                for asset_class in data_plot['Asset Class'].unique():
                    if pd.notna(asset_class): subset = data_plot[data_plot['Asset Class'] == asset_class]; ax_scatter.scatter(subset['Beta (vs Benchmark)'], subset['Volatilite Annuelle'] * 100, label=asset_class, s=120, alpha=0.8, color=class_colors.get(asset_class, COLORS['text_secondary']), edgecolors=COLORS['text_primary'], linewidth=1.5)
                ax_scatter.set_xlabel('BETA (VS BENCHMARK)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_scatter.set_ylabel('ANNUAL VOLATILITY (%)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_scatter.set_title('RISK-BETA ANALYSIS', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); ax_scatter.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid']); ax_scatter.tick_params(colors=COLORS['text_secondary']); ax_scatter.spines['bottom'].set_color(COLORS['border']); ax_scatter.spines['top'].set_color(COLORS['border']); ax_scatter.spines['left'].set_color(COLORS['border']); ax_scatter.spines['right'].set_color(COLORS['border'])
                legend = ax_scatter.legend(loc='best', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9); [text.set_color(COLORS['text_primary']) for text in legend.get_texts()]
                ax_scatter.axvline(1.0, color=COLORS['text_secondary'], linestyle='--', alpha=0.5, linewidth=1.5); fig_scatter.tight_layout(); st.pyplot(fig_scatter)
                st.markdown("---")
                st.markdown("### SHARPE RATIO VS VOLATILITY")
                data_plot_sharpe = data_plot.dropna(subset=['Sharpe Ratio Annuel'])
                if not data_plot_sharpe.empty:
                    fig_sharpe, ax_sharpe = plt.subplots(figsize=(12, 7)); fig_sharpe.patch.set_facecolor(COLORS['bg_dark']); ax_sharpe.set_facecolor(COLORS['bg_panel'])
                    for asset_class in data_plot_sharpe['Asset Class'].unique():
                        if pd.notna(asset_class): subset = data_plot_sharpe[data_plot_sharpe['Asset Class'] == asset_class]; ax_sharpe.scatter(subset['Volatilite Annuelle'] * 100, subset['Sharpe Ratio Annuel'], label=asset_class, s=120, alpha=0.8, color=class_colors.get(asset_class, COLORS['text_secondary']), edgecolors=COLORS['text_primary'], linewidth=1.5)
                    ax_sharpe.set_xlabel('ANNUAL VOLATILITY (%)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_sharpe.set_ylabel('SHARPE RATIO (ANN.)', fontsize=11, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); ax_sharpe.set_title('RISK-ADJUSTED RETURN', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); ax_sharpe.grid(True, alpha=0.2, linestyle='--', linewidth=0.5, color=COLORS['grid']); ax_sharpe.tick_params(colors=COLORS['text_secondary']); ax_sharpe.spines['bottom'].set_color(COLORS['border']); ax_sharpe.spines['top'].set_color(COLORS['border']); ax_sharpe.spines['left'].set_color(COLORS['border']); ax_sharpe.spines['right'].set_color(COLORS['border'])
                    legend = ax_sharpe.legend(loc='best', frameon=True, facecolor=COLORS['bg_panel'], edgecolor=COLORS['border'], fontsize=9); [text.set_color(COLORS['text_primary']) for text in legend.get_texts()]
                    ax_sharpe.axhline(0, color=COLORS['text_secondary'], linestyle='--', alpha=0.5, linewidth=1.5); fig_sharpe.tight_layout(); st.pyplot(fig_sharpe)
                else: st.warning("Insufficient Sharpe data")
            else: st.warning("No data to display")
        with subtab3:
            st.markdown("### CORRELATION MATRIX"); st.caption("Calculated over full historical period")
            if corr_matrix is not None and not corr_matrix.empty:
                col1, col2, col3, col4 = st.columns(4); corr_values = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]; col1.metric("AVG CORR", f"{corr_values.mean():.2f}"); col2.metric("MAX CORR", f"{corr_values.max():.2f}"); col3.metric("MIN CORR", f"{corr_values.min():.2f}"); col4.metric("STD DEV", f"{corr_values.std():.2f}")
                st.markdown("---")
                all_assets = corr_matrix.columns.tolist(); col_filter1, col_filter2 = st.columns(2)
                with col_filter1: show_all = st.checkbox("SHOW ALL ASSETS", value=True)
                if not show_all:
                    with col_filter2: n_assets = st.slider("NUMBER OF ASSETS", min_value=5, max_value=min(50, len(all_assets)), value=min(20, len(all_assets))); selected_assets = all_assets[:n_assets]; corr_display = corr_matrix.loc[selected_assets, selected_assets]
                else: corr_display = corr_matrix
                styled_corr = corr_display.style.background_gradient(cmap='coolwarm', vmin=-1, vmax=1).format("{:.2f}", na_rep='N/A')
                st.dataframe(styled_corr, use_container_width=True, height=600)
                csv_corr = corr_display.to_csv().encode('utf-8'); st.download_button("DOWNLOAD MATRIX", csv_corr, "correlation_matrix.csv", "text/csv", key='download_corr')
                st.markdown("---")
                st.markdown("### CORRELATION HEATMAP")
                fig_heatmap, ax_heatmap = plt.subplots(figsize=(14, 12)); fig_heatmap.patch.set_facecolor(COLORS['bg_dark'])
                if len(corr_display) > 30: st.info(f"Display limited to first 30 assets"); corr_viz = corr_display.iloc[:30, :30]
                else: corr_viz = corr_display
                im = ax_heatmap.imshow(corr_viz, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                cbar = plt.colorbar(im, ax=ax_heatmap); cbar.set_label('CORRELATION', rotation=270, labelpad=20, fontsize=10, fontweight='600', color=COLORS['text_primary'], fontfamily='monospace'); cbar.ax.tick_params(colors=COLORS['text_secondary'])
                ax_heatmap.set_xticks(range(len(corr_viz.columns))); ax_heatmap.set_yticks(range(len(corr_viz.index))); ax_heatmap.set_xticklabels(corr_viz.columns, rotation=90, fontsize=7, color=COLORS['text_secondary']); ax_heatmap.set_yticklabels(corr_viz.index, fontsize=7, color=COLORS['text_secondary']); ax_heatmap.set_title('CORRELATION HEATMAP', fontsize=13, fontweight='700', pad=15, color=COLORS['accent_orange'], fontfamily='monospace'); fig_heatmap.tight_layout(); st.pyplot(fig_heatmap)
            else: st.error("Correlation matrix unavailable")
    else: st.error("Analytics data unavailable")

# --- Footer Bloomberg Style ---
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1: st.caption("M2 MBFA TERMINAL")
with col2: st.caption(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
with col3: st.caption("v2.7 DRIFT FIX") # Version mise à jour