# nlp_chatbot_analytics

Conversational AI / chatbot performance analytics on **9,795 real customer-support conversations** across **108 real brand support accounts** (Twitter Customer Support dataset — Amazon, Apple, Uber, Delta, Spotify, T-Mobile, and more).

Added as a module inside the order-ops project because the same operational question applies: a WhatsApp-first SMB order platform runs AI agents over a messaging channel, so knowing *which conversations a bot can handle alone vs. which need a human* is the same problem as intent classification + escalation tracking here.

## What's genuinely "AI/NLP" here (and what isn't)

- **Not the deliverable:** a documented, rule-based first pass labels each conversation's opening message into one of 7 intents. This is a standard *weak-supervision* technique for bootstrapping training data — not a claim of AI by itself.
- **The actual deliverable:** a **TF-IDF + Logistic Regression classifier** trained on an 80/20 split of those weak labels, evaluated on **held-out test data it never saw during training**. Every downstream chart uses the trained model's predictions, not the raw rules.

## Results (held-out test set)

- **96.1% accuracy**, **0.913 macro F1** across 7 intent classes (macro F1 matters here since ~75% of conversations fall in a dominant "other" class — a trivial majority-class baseline would score far lower than 0.91 on macro F1).
- Per-class F1 ranges 0.81–0.98 (worst: `technical_issue` at 0.81; best: `other` at 0.98) — see the full classification report and confusion matrix in [`reports/nlp_report.md`](reports/nlp_report.md).

## Chatbot performance findings

- **32.9%** of conversations get pushed to a private DM — used here as an escalation-to-human proxy, since this dataset has one timestamp per conversation (not per message), so true first-response-time isn't computable.
- Complaints and billing/refund intents escalate to DM well above average (48% and 43% vs. 32.9% overall) — exactly the intents an AI agent should route to a human fastest.
- Escalation rate varies enormously by brand (2% for AmazonHelp vs. 86-90% for comcastcares/TMobileHelp), showing this is a company-specific support-process signal, not just a property of the conversation content.

## Reproducing this

```
pip install -r ../requirements.txt scikit-learn
python python/nlp_intent_and_performance.py
```

Outputs `reports/nlp_report.md`, 3 charts in `reports/figures/`, and `data/processed_conversations.csv` (consumed by the live Streamlit page in `../streamlit_app/pages/1_Chatbot_Analytics.py`).

## Data source

[Twitter Customer Support conversations](https://huggingface.co/datasets/jphwang/twitter_customer_support_weaviate_export_200000_nomic-embed-text) (text + metadata extracted; embedding vectors dropped), derived from the public [Kaggle Customer Support on Twitter dataset](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter). Real, anonymized conversations — not synthetic.
