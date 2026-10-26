# Elsevier_TDM

```extract_elsevier_text.py``` downloads article full text in XML from the Elsevier ScienceDirect API using a list of DOIs and an API key, with optional institutional-token authentication. Preserves the original XML and creates a readable UTF-8 text file containing the title, abstract, section headings, and main text. Excludes reference lists, tables, and figure captions from the text output, and reports download errors or missing article-body content.

```extract_elsevier_text.py```reads a list of DOIs from a textfile supplied as a command-line argument and downloads article full text in XML from the Elsevier ScienceDirect API. Accepts plain DOIs or DOI links, ignores blank lines and comments, and removes duplicates. Preserves the original XML and creates readable UTF-8 text files containing the title, abstract, section headings, and main text, excluding reference lists, tables, and figure captions. Processes articles sequentially and reports download errors or missing article-body content.  
```python extract_elsevier_text.py dois.txt```
