# Elsevier_TDM

```extract_elsevier_text.py``` downloads article full text from the Elsevier ScienceDirect API using a list of DOIs and an API key, with optional institutional-token authentication. Preserves the original XML and creates a readable UTF-8 text file containing the title, abstract, section headings, and main text. Excludes reference lists, tables, and figure captions from the text output, and reports download errors or missing article-body content.
