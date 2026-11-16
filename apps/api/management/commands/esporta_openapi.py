"""Scrive lo schema OpenAPI di /api/v1 in un file (da lì `npm run api:tipi` genera i tipi TS)."""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Esporta lo schema OpenAPI dell'API v1 in formato JSON."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="File di destinazione")

    def handle(self, *args, output: str, **options):
        from apps.api.api import api

        schema = api.get_openapi_schema()
        with open(output, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2, sort_keys=True)
        self.stdout.write(f"Schema OpenAPI scritto in {output}")
