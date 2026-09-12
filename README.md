# atmosphericdust.com

Static site. Content lives in the YAML files under `data/`; `build.py` turns them
into `index.html` and `publications.html`.

```bash
pip install pyyaml
python3 build.py
```

Do not edit the HTML by hand — it is overwritten on every build.
