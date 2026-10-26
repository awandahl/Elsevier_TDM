#!/usr/bin/env python3

import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import requests


ARTICLES = [
    {
        "doi": "10.1016/j.colsurfb.2024.113769",
        "title": (
            "Nano-FTIR spectroscopy of surface confluent "
            "polydopamine films"
        ),
    },
    {
        "doi": "10.1016/j.drudis.2024.103908",
        "title": (
            "Structural-functional analysis of drug target "
            "aspartate semialdehyde dehydrogenase"
        ),
    },
    {
        "doi": "10.1016/j.scitotenv.2022.160405",
        "title": (
            "Analyzing the relationship between product waste "
            "footprints and environmental damage"
        ),
    },
]

OUTPUT_DIR = Path("elsevier_xml")
REDIRECT_CODES = {301, 302, 303, 307, 308}


def redact(text, secrets):
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def retrieve_xml(doi, api_key, insttoken):
    encoded_doi = quote(doi, safe="/")
    url = f"https://api.elsevier.com/content/article/doi/{encoded_doi}"
    params = {"httpAccept": "application/xml"}

    for _ in range(6):
        parsed = urlsplit(url)

        if parsed.scheme != "https":
            raise RuntimeError("Refusing a non-HTTPS URL")

        headers = {"Accept": "application/xml"}

        # Never forward credentials to a different host.
        if parsed.hostname == "api.elsevier.com":
            headers["X-ELS-APIKey"] = api_key
            if insttoken:
                headers["X-ELS-Insttoken"] = insttoken

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=(15, 120),
            allow_redirects=False,
        )

        if response.status_code not in REDIRECT_CODES:
            return response

        location = response.headers.get("Location")
        if not location:
            raise RuntimeError("Redirect has no Location header")

        url = urljoin(url, location)
        params = None

    raise RuntimeError("Too many redirects")


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def has_body_text(root):
    return any(
        local_name(element.tag).lower() == "body"
        and any(text.strip() for text in element.itertext())
        for element in root.iter()
    )


def show_response_preview(response, secrets):
    preview = response.content[:1500].decode(
        "utf-8", errors="replace"
    )
    print(redact(preview, secrets))

def element_name(element):
    return element.tag.rsplit("}", 1)[-1]


def normalized_text(element):
    # Join inline XML content before normalizing whitespace.
    # This preserves words split across inline markup.
    return " ".join("".join(element.itertext()).split())


def first_descendant(element, name):
    return next(
        (
            child
            for child in element.iter()
            if element_name(child) == name
        ),
        None,
    )


def readable_article_text(root, doi):
    # Prefer the actual publisher article, not API/index metadata.
    original = first_descendant(root, "originalText")
    source = original if original is not None else root

    article = first_descendant(source, "article")
    if article is None:
        article = source

    head = first_descendant(article, "head")
    body = first_descendant(article, "body")

    if body is None:
        raise ValueError("No article <body> found; refusing metadata-only text")

    lines = []

    title = (
        first_descendant(head, "title")
        if head is not None
        else None
    )

    if title is not None:
        title_text = normalized_text(title)
        if title_text:
            lines.extend([title_text, "=" * len(title_text), ""])

    lines.extend([f"DOI: {doi}", ""])

    # Restrict abstract selection to the article header.
    if head is not None:
        for abstract in head.iter():
            if element_name(abstract) != "abstract":
                continue

            # Exclude highlights and graphical abstracts.
            abstract_class = abstract.get("class", "").lower()
            if abstract_class not in {"", "author"}:
                continue

            paragraphs = [
                normalized_text(element)
                for element in abstract.iter()
                if element_name(element) in {"simple-para", "para"}
            ]
            paragraphs = [text for text in paragraphs if text]

            if paragraphs:
                lines.extend(["ABSTRACT", ""])
                lines.extend(paragraphs)
                lines.append("")
                break

    lines.extend(["MAIN TEXT", ""])

    excluded = {
        "bibliography",
        "bib-reference",
        "figure",
        "table",
        "table-wrap",
        "caption",
        "label",
        "section-title",
    }

    def render(element):
        name = element_name(element)

        if name in excluded:
            return

        if name == "section":
            label = next(
                (
                    normalized_text(child)
                    for child in element
                    if element_name(child) == "label"
                ),
                "",
            )
            heading = next(
                (
                    normalized_text(child)
                    for child in element
                    if element_name(child) == "section-title"
                ),
                "",
            )

            heading = " ".join(
                part for part in (label, heading) if part
            )
            if heading:
                lines.extend([heading, ""])

            for child in element:
                render(child)
            return

        if name in {"para", "simple-para"}:
            text = normalized_text(element)
            if text:
                lines.extend([text, ""])
            return

        if name == "list-item":
            text = normalized_text(element)
            if text:
                lines.extend([f"- {text}", ""])
            return

        for child in element:
            render(child)

    render(body)

    return "\n".join(lines).strip() + "\n"

def main():
    api_key = os.environ.get("ELSEVIER_API_KEY", "").strip()
    insttoken = os.environ.get("ELSEVIER_INSTTOKEN", "").strip()
    secrets = (api_key, insttoken)

    if not api_key:
        sys.exit("Set the ELSEVIER_API_KEY environment variable first.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    for index, article in enumerate(ARTICLES, start=1):
        doi = article["doi"]
        print(f"\n[{index}/{len(ARTICLES)}] {article['title']}")
        print(f"  DOI: {doi}")

        try:
            response = retrieve_xml(doi, api_key, insttoken)

            print(
                f"  HTTP {response.status_code}; "
                f"Content-Type: "
                f"{response.headers.get('Content-Type', '')}"
            )

            for name, value in response.headers.items():
                if name.lower().startswith("x-els"):
                    print(f"  {name}: {redact(value, secrets)}")

            if response.status_code != 200:
                print("  Download failed. Response preview:")
                show_response_preview(response, secrets)
                continue

            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as exc:
                print(f"  Response is not well-formed XML: {exc}")
                show_response_preview(response, secrets)
                continue

            root_name = local_name(root.tag).lower()
            if root_name in {"html", "error", "service-error"}:
                print(f"  Unexpected response root: {root_name}")
                show_response_preview(response, secrets)
                continue

            filename = doi.replace("/", "_") + ".xml"
            destination = OUTPUT_DIR / filename

            # Preserve the original response bytes and encoding.
            destination.write_bytes(response.content)

            try:
                text = readable_article_text(root, doi)
                text_destination = destination.with_suffix(".txt")
                text_destination.write_text(text, encoding="utf-8")
                print(f"  Readable text saved: {text_destination}")
            except (ValueError, OSError) as exc:
                print(f"  XML saved, but text extraction failed: {exc}")
            downloaded += 1

            print(
                f"  Saved: {destination} "
                f"({len(response.content):,} bytes)"
            )

            if has_body_text(root):
                print("  Non-empty article <body> detected.")
            else:
                print(
                    "  WARNING: No non-empty <body> detected. "
                    "Inspect the XML: it may contain only metadata "
                    "and an abstract, or use a different structure."
                )

        except (requests.RequestException, RuntimeError, OSError) as exc:
            message = redact(str(exc), secrets)
            print(f"  Failed: {type(exc).__name__}: {message}")

        finally:
            if index < len(ARTICLES):
                time.sleep(1)

    print(f"\nSaved {downloaded}/{len(ARTICLES)} XML responses.")
    return 0 if downloaded == len(ARTICLES) else 1


if __name__ == "__main__":
    sys.exit(main())