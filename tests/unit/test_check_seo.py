from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[2]
SITE_URL = "https://example.github.io/project/"
GOOD_DESCRIPTION = "A description that is long enough for search engines to show it."
JSON_LD = '<script type="application/ld+json">{"@type": "SoftwareApplication"}</script>'


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_seo", ROOT / "scripts" / "check_seo.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


check_seo = load_script()


def page(
    url: str,
    title: str,
    *,
    description: str | None = GOOD_DESCRIPTION,
    og_image: bool = True,
    extra: str = "",
) -> str:
    head = [f"<title>{title}</title>", f'<link rel="canonical" href="{url}">']
    if description is not None:
        head.append(f'<meta name="description" content="{description}">')
    if og_image:
        head.append(f'<meta property="og:image" content="{url}card.png">')
    return f"<html><head>{''.join(head)}{extra}</head><body></body></html>"


def build_site(
    root: Path,
    pages: dict[str, str],
    *,
    sitemap: list[str] | None = None,
    llms: bool = True,
    not_found: bool = True,
) -> Path:
    for relative, html in pages.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    urls = sitemap if sitemap is not None else [SITE_URL, f"{SITE_URL}tools/"]
    locations = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    sitemap_xml = (
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locations}</urlset>'
    )
    (root / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    if llms:
        (root / "llms.txt").write_text("# Project\n\n- [Home](https://x/)\n", encoding="utf-8")
    if not_found:
        (root / "404.html").write_text(
            "<html><head><title>404</title></head></html>", encoding="utf-8"
        )
    return root


def good_pages() -> dict[str, str]:
    return {
        "index.html": page(SITE_URL, "Home - Project", extra=JSON_LD),
        "tools/index.html": page(f"{SITE_URL}tools/", "Tools - Project"),
    }


def test_a_complete_site_has_no_problems(tmp_path: Path) -> None:
    assert check_seo.check_site(build_site(tmp_path, good_pages())) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"tools/index.html": page(f"{SITE_URL}tools/", "Home - Project")}, "also used by"),
        (
            {"tools/index.html": page(f"{SITE_URL}tools/", "Tools", description="Too short")},
            "description is 9 characters",
        ),
        (
            {"tools/index.html": page(f"{SITE_URL}tools/", "Tools", description=None)},
            "no meta description",
        ),
        ({"tools/index.html": page(f"{SITE_URL}tools/", "Tools", og_image=False)}, "no og:image"),
        ({"index.html": page(SITE_URL, "Home - Project")}, "no SoftwareApplication JSON-LD"),
    ],
)
def test_each_page_problem_is_reported(
    tmp_path: Path, change: dict[str, str], problem: str
) -> None:
    site = build_site(tmp_path, {**good_pages(), **change})

    assert any(problem in reported for reported in check_seo.check_site(site))


@pytest.mark.parametrize(
    ("options", "problem"),
    [
        ({"sitemap": [SITE_URL]}, "tools/index.html: canonical URL is not in sitemap.xml"),
        ({"llms": False}, "llms.txt is missing or empty"),
        ({"not_found": False}, "404.html is missing"),
    ],
)
def test_each_site_problem_is_reported(
    tmp_path: Path, options: dict[str, object], problem: str
) -> None:
    site = build_site(tmp_path, good_pages(), **options)  # type: ignore[arg-type]

    assert problem in check_seo.check_site(site)


def test_command_exits_with_1_and_lists_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = build_site(tmp_path, good_pages(), llms=False)

    exit_code = check_seo.main([str(site)])

    assert exit_code == 1
    assert "llms.txt is missing or empty" in capsys.readouterr().out
