# INSIGHT

Current standalone application:

- [`Modules/Authentication-1.1.0/`](Modules/Authentication-1.1.0/) -
  Authentication service and UI, including INS-013 UUID session contract.

## Run Authentication

```bash
cd Modules/Authentication-1.1.0
python3 -m pip install -r requirements.txt
python3 main.py
```

Open `http://localhost:8000/`.

## Test

```bash
cd Modules/Authentication-1.1.0
python3 -B -m unittest discover -s tests -v
```

Module contracts and documentation are under
[`Modules/Authentication-1.1.0/docs/`](Modules/Authentication-1.1.0/docs/).
