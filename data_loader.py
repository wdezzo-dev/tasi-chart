import os
import streamlit as st
import pandas as pd


@st.cache_data(ttl=300)
def load_table(interval: str, table_idx: int) -> pd.DataFrame:
    path = f"data/{interval}/table_{table_idx}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    return pd.DataFrame()
