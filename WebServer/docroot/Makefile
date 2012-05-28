######################################
%.html: %.haml
	haml -f html5 $^ $@
######################################
HTML= index.html

######################################
all: ${HTML}
	cd stylesheets; make

clean:
	rm -f ${HTML}
	cd stylesheets; make clean
