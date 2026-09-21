"""Validate the generated site's metadata, navigation and local assets using stdlib."""
import json
import hashlib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "public"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.in_json = False
        self.buffer = ""
        self.schemas = []
        self.canonical = []
        self.descriptions = []
        self.h1 = 0
        self.references = []
        self.images = []
        self.missing_image_alt = []
        self.anchors = set()
        self.breadcrumbs = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.anchors.add(attrs["id"])
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "nav" and attrs.get("aria-label") == "Breadcrumb":
            self.breadcrumbs += 1
        if tag == "meta" and attrs.get("name") == "description":
            self.descriptions.append(attrs.get("content", ""))
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs["href"])
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_json = True
            self.buffer = ""
        key = "href" if tag in ("a", "link") else "src"
        if tag in ("a", "link", "img", "script") and attrs.get(key):
            self.references.append(attrs[key])
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
            classes = attrs.get("class", "").split()
            if not (attrs.get("alt") or "").strip() and "product-card-img-hover" not in classes:
                self.missing_image_alt.append(attrs["src"])

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_json:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_json:
            self.schemas.append(json.loads(self.buffer))
            self.in_json = False


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    urls = [node.text for node in ET.parse(ROOT / "sitemap.xml").findall(
        ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    pages = {}
    for url in urls:
        page = Page()
        page.feed((ROOT / urlsplit(url).path.lstrip("/") / "index.html").read_text(encoding="utf-8"))
        pages[url] = page
    titles = Counter(page.title for page in pages.values())
    descriptions = Counter(page.descriptions[0] for page in pages.values() if page.descriptions)
    for url, page in pages.items():
        require(page.title and titles[page.title] == 1, f"{url}: missing or duplicate title")
        require(len(page.descriptions) == 1 and page.descriptions[0], f"{url}: missing description")
        require(descriptions[page.descriptions[0]] == 1, f"{url}: duplicate description")
        require(page.canonical == [url], f"{url}: canonical mismatch")
        require(page.h1 == 1, f"{url}: expected one H1")
        require(not page.missing_image_alt, f"{url}: missing image alt text {page.missing_image_alt}")
        image_bytes = 0
        image_identities = Counter()
        for ref in page.images:
            target = urlsplit(urljoin(url, ref))
            if target.netloc == urlsplit(url).netloc:
                image_path = ROOT / unquote(target.path).lstrip("/")
                if image_path.is_file():
                    image_identities[hashlib.sha256(image_path.read_bytes()).hexdigest()] += 1
        require(
            not image_identities or max(image_identities.values()) <= 2,
            f"{url}: the same image appears more than twice",
        )
        for ref in set(page.images):
            target = urlsplit(urljoin(url, ref))
            if target.netloc == urlsplit(url).netloc:
                image_path = ROOT / unquote(target.path).lstrip("/")
                if image_path.is_file():
                    image_bytes += image_path.stat().st_size
        require(image_bytes <= 8_000_000, f"{url}: image payload exceeds 8 MB")
        crumbs = [item for item in page.schemas if item.get("@type") == "BreadcrumbList"]
        if urlsplit(url).path != "/":
            require(len(crumbs) == 1 and page.breadcrumbs == 1, f"{url}: breadcrumb count")
            items = crumbs[0]["itemListElement"]
            require(items[-1]["item"] == url, f"{url}: breadcrumb endpoint")
            require([item["position"] for item in items] == list(range(1, len(items) + 1)), f"{url}: breadcrumb order")
            require(all(item["item"] in pages for item in items), f"{url}: breadcrumb target")
        for schema in page.schemas:
            if schema.get("@type") == "CollectionPage":
                items = schema["mainEntity"]["itemListElement"]
                require(bool(items), f"{url}: empty collection")
                require(all(item["url"] in pages for item in items), f"{url}: collection target")
                require(all(item["url"] in [urljoin(url, ref) for ref in page.references] for item in items), f"{url}: collection not visible")
        for ref in page.references:
            target = urlsplit(urljoin(url, ref))
            if target.scheme not in ("http", "https") or target.netloc != urlsplit(url).netloc:
                continue
            path = ROOT / unquote(target.path).lstrip("/")
            require(path.is_file() or (path / "index.html").is_file(), f"{url}: missing local target {ref}")
            if target.fragment:
                target_url = target._replace(fragment="", query="").geturl()
                target_page = pages.get(target_url) or pages.get(target_url.rstrip("/") + "/")
                if target_page:
                    require(unquote(target.fragment) in target_page.anchors, f"{url}: missing anchor {ref}")
    print(f"PASS: {len(pages)} sitemap pages; unique metadata, H1, image alt text, canonicals, JSON-LD, breadcrumbs, collection links, local assets and anchors.")


if __name__ == "__main__":
    main()
