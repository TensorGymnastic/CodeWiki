import json

from click.testing import CliRunner

from codewiki.cli.main import cli
from codewiki.src.enduser.io import load_enduser_catalog


def test_enduser_extract_playwright_writes_catalog_yaml(tmp_path):
    crawl_path = tmp_path / "crawl.json"
    output_path = tmp_path / "catalog.yaml"
    crawl_path.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "route": "/customers/edit",
                        "title": "Customer Edit",
                        "fields": [
                            {
                                "name": "customer_name",
                                "label": "Customer Name",
                                "role": "textbox",
                            }
                        ],
                        "actions": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["enduser", "extract-playwright", str(crawl_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()

    catalog = load_enduser_catalog(output_path)
    assert [page.id for page in catalog.pages] == ["page.customers_edit"]
    assert [field.id for field in catalog.fields] == ["field.customers_edit.customer_name"]
