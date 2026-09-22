"""
Conversational AI / chatbot performance page.

Visualizes the precomputed output of nlp_chatbot_analytics/python/
nlp_intent_and_performance.py (a real TF-IDF + Logistic Regression intent
classifier trained on real Twitter customer-support conversations). The
classifier itself is trained offline; this page reads its saved predictions
so the deployed app stays lightweight.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
NLP_ROOT = ROOT / "nlp_chatbot_analytics"

st.set_page_config(page_title="Chatbot Analytics", page_icon="\U0001F4AC", layout="wide")


@st.cache_data
def load():
    return pd.read_csv(NLP_ROOT / "data" / "processed_conversations.csv")


df = load()

st.title("Conversational AI / Chatbot Performance")
st.caption(
    f"{len(df):,} real customer-support conversations across {df['company_author'].nunique()} "
    "real brand support accounts (Twitter Customer Support dataset). Intent is predicted by a "
    "TF-IDF + Logistic Regression classifier trained on weak-supervision labels — full "
    "methodology and held-out accuracy in "
    "[`nlp_chatbot_analytics/reports/nlp_report.md`](https://github.com/achi-vyshnavi28/whatsapp-order-ops-analytics/blob/main/nlp_chatbot_analytics/reports/nlp_report.md)."
)

c1, c2, c3 = st.columns(3)
c1.metric("Conversations analyzed", f"{len(df):,}")
c2.metric("Avg turns per conversation", f"{df['n_turns'].mean():.1f}")
c3.metric("Escalated to private DM", f"{df['escalated_to_dm'].mean():.1%}")

st.divider()

companies = st.multiselect(
    "Filter by brand", sorted(df["company_author"].value_counts().head(20).index),
    default=list(df["company_author"].value_counts().head(6).index),
)
view = df[df["company_author"].isin(companies)] if companies else df

left, right = st.columns(2)

with left:
    st.subheader("Conversation Volume by Predicted Intent")
    intent_counts = view["predicted_intent"].value_counts().reset_index()
    intent_counts.columns = ["intent", "conversations"]
    fig = px.bar(intent_counts, x="conversations", y="intent", orientation="h",
                 color_discrete_sequence=["#0f7a6c"])
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="", height=420)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Private-Channel (DM) Escalation Rate by Intent")
    esc = view.groupby("predicted_intent")["escalated_to_dm"].mean().sort_values(ascending=False).reset_index()
    fig2 = px.bar(esc, x="escalated_to_dm", y="predicted_intent", orientation="h",
                  color_discrete_sequence=["#c1443a"])
    fig2.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="",
                        xaxis_title="Share escalated to DM", xaxis_tickformat=".0%", height=420)
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Performance by Brand")
by_company = (
    view.groupby("company_author")
    .agg(conversations=("dialogue_id", "count"), avg_turns=("n_turns", "mean"),
         dm_escalation_rate=("escalated_to_dm", "mean"))
    .sort_values("conversations", ascending=False)
)
by_company["dm_escalation_rate"] = (by_company["dm_escalation_rate"] * 100).round(1)
by_company["avg_turns"] = by_company["avg_turns"].round(2)
st.dataframe(
    by_company.rename(columns={"conversations": "Conversations", "avg_turns": "Avg Turns",
                                "dm_escalation_rate": "DM Escalation Rate (%)"}),
    use_container_width=True,
)

st.divider()
st.subheader("Classifier Evaluation")
st.caption("Held-out test-set confusion matrix for the intent classifier (fixed evaluation artifact, not filtered by the selection above).")
st.image(str(NLP_ROOT / "reports" / "figures" / "nlp_01_confusion_matrix.png"), width=600)

st.caption(
    "Data source: [Twitter Customer Support conversations](https://huggingface.co/datasets/jphwang/twitter_customer_support_weaviate_export_200000_nomic-embed-text) "
    "(derived from the public Kaggle Customer Support on Twitter dataset). Built with Streamlit, Pandas, scikit-learn, and Plotly."
)
