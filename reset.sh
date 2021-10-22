echo "try:\n    compile(open('reset0.py').read())\nexcept Exception:\n    compile(open('reset1.py').read())" > tmp.py
python tmp.py