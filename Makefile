.PHONY: manual screenshots

MANUAL_DIR  = docs/manuale
MANUAL_PDF  = $(MANUAL_DIR)/plancia_manuale.pdf
MANUAL_SRC  = $(MANUAL_DIR)/index.md \
              $(MANUAL_DIR)/csq.md \
              $(MANUAL_DIR)/crp.md \
              $(MANUAL_DIR)/pgv.md \
              $(MANUAL_DIR)/incaricato.md \
              $(MANUAL_DIR)/segreteria.md \
              $(MANUAL_DIR)/admin.md

manual: $(MANUAL_PDF)

$(MANUAL_PDF): $(MANUAL_SRC)
	cd $(MANUAL_DIR) && pandoc \
	  --pdf-engine=xelatex \
	  --toc --toc-depth=2 \
	  -V title="Plancia — Manuale d'uso" \
	  -V subtitle="Guidoncini Verdi · AGESCI Campania" \
	  -V date="$$(date +'%B %Y')" \
	  -V lang="it" \
	  -V geometry="margin=2.5cm" \
	  -V fontsize="11pt" \
	  -V colorlinks=true \
	  -V linkcolor="teal" \
	  -V urlcolor="teal" \
	  -V toccolor="teal" \
	  -V linestretch="1.25" \
	  --syntax-highlighting=tango \
	  index.md csq.md crp.md pgv.md incaricato.md segreteria.md admin.md \
	  -o plancia_manuale.pdf
	@echo "PDF generato: $(MANUAL_PDF)"

screenshots:
	uv run python $(MANUAL_DIR)/seed_e_screenshot.py
