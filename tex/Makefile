SHELL = /bin/bash

PDFLATEX = pdflatex -output-directory pdf
TEXTRASH = aux log


all: $(foreach I, $(wildcard *.tex), jpg/$(basename $I).jpg)
	:


jpg/%.jpg: pdf/%.pdf
	[ -d "jpg" ] || mkdir jpg; \
	convert -density 110 "$<" -quality 90 "$@"


.PRECIOUS : pdf/%.pdf

pdf/%.pdf: %.tex db.sty
	[ -d "pdf" ] || mkdir pdf; \
	$(PDFLATEX) $<; \
	rm -rf $(foreach I, $(TEXTRASH), pdf/$(basename $<).$I)


clean:
	rm -rf pdf jpg
